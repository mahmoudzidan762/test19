# -*- coding: utf-8 -*-

import logging
from markupsafe import Markup, escape
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class FieldTrackerMixin(models.AbstractModel):
    _name = 'field.tracker.mixin'
    _description = 'Auto Field Tracker Mixin (internal)'


class FieldTrackerService(models.AbstractModel):
    """
    Core engine. Provides snapshot / diff / chatter / log methods.
    Called from the ORM hooks below.
    """
    _name = 'field.tracker.service'
    _description = 'Auto Field Tracker Service'

    # ─── Cache helpers ───────────────────────────────────────────────

    @api.model
    def _get_config_cache(self):
        """
        Return a simple per-transaction cache dict stored on the cursor.
        Avoids hammering the DB on every single write() call.
        """
        if not hasattr(self.env.cr, '_aft_config_cache'):
            self.env.cr._aft_config_cache = {}
        return self.env.cr._aft_config_cache

    @api.model
    def get_active_config(self, model_name):
        """
        Return the active FieldTrackerConfig for a model name, or empty recordset.
        Result is cached per DB cursor to avoid repeated SQL on every write.
        """
        cache = self._get_config_cache()
        if model_name in cache:
            cached_id = cache[model_name]
            if not cached_id:
                return self.env['field.tracker.config'].browse()
            config = self.env['field.tracker.config'].browse(cached_id)
            if config.exists():
                return config

        config = self.env['field.tracker.config'].search([
            ('model_name', '=', model_name),
            ('active', '=', True),
        ], limit=1)
        cache[model_name] = config.id if config else False
        return config

    @api.model
    def get_parent_o2m_specs(self, child_model_name):
        """
        Return parent tracker configs whose selected One2many fields point to
        child_model_name. Example: sale.order.order_line -> sale.order.line.
        """
        cache = self._get_config_cache()
        cache_key = ('o2m_specs', child_model_name)
        if cache_key in cache:
            return self._expand_parent_o2m_specs(cache[cache_key])

        specs = []
        configs = self.env['field.tracker.config'].search([
            ('active', '=', True),
            ('track_o2m_lines', '=', True),
            ('o2m_field_ids.relation', '=', child_model_name),
        ])
        for config in configs:
            parent_model = self.env[config.model_name]
            child_model = self.env[child_model_name]
            for o2m_field in config.o2m_field_ids.filtered(lambda f: f.relation == child_model_name):
                inverse_name = o2m_field.relation_field
                parent_field = parent_model._fields.get(o2m_field.name)
                if not inverse_name and parent_field:
                    inverse_name = getattr(parent_field, 'inverse_name', False)
                if (
                    inverse_name
                    and inverse_name in child_model._fields
                    and child_model._fields[inverse_name].type == 'many2one'
                ):
                    specs.append((config.id, o2m_field.name, o2m_field.field_description, inverse_name))

        cache[cache_key] = specs
        return self._expand_parent_o2m_specs(specs)

    @api.model
    def _expand_parent_o2m_specs(self, specs):
        return [{
            'config': self.env['field.tracker.config'].browse(config_id),
            'o2m_field_name': o2m_field_name,
            'o2m_field_label': o2m_field_label,
            'inverse_name': inverse_name,
        } for config_id, o2m_field_name, o2m_field_label, inverse_name in specs]

    @api.model
    def get_trackable_field_names_for_model(self, model_name, inverse_name=False):
        """Return storable editable fields for a child model."""
        model_cls = self.env[model_name]
        skip_types = {'one2many', 'many2many', 'binary'}
        skip_names = {
            'id', 'create_uid', 'create_date', 'write_uid', 'write_date',
            '__last_update', 'message_ids', 'message_follower_ids',
            'activity_ids', 'message_is_follower', 'message_needaction',
            'message_needaction_counter', 'activity_state',
        }
        if inverse_name:
            skip_names.add(inverse_name)
        return [
            name for name, field in model_cls._fields.items()
            if field.type not in skip_types
            and name not in skip_names
            and getattr(field, 'store', True)
            and not getattr(field, 'related', None)
            and not (getattr(field, 'compute', None) and getattr(field, 'readonly', False))
        ]

    # ─── Snapshot ────────────────────────────────────────────────────

    @api.model
    def capture_old_values(self, records, field_names):
        """
        Snapshot current display values for field_names before a write.
        Returns: {record_id: {field_name: display_string}}
        """
        snapshot = {}
        for record in records:
            snapshot[record.id] = {}
            for fname in field_names:
                try:
                    snapshot[record.id][fname] = self._get_display_value(record, fname)
                except Exception as e:
                    _logger.debug('AFT snapshot error %s.%s: %s', record._name, fname, e)
                    snapshot[record.id][fname] = None
        return snapshot

    @api.model
    def prepare_o2m_write_tracking(self, records, vals):
        """Snapshot child-line values for selected parent One2many trackers."""
        snapshots = []
        for spec in self.get_parent_o2m_specs(records._name):
            config = spec['config']
            if not config or not config.log_on_write:
                continue
            inverse_name = spec['inverse_name']
            tracked_fields = self.get_trackable_field_names_for_model(records._name, inverse_name)
            changed_fields = [fname for fname in tracked_fields if fname in vals]
            if not changed_fields:
                continue
            parent_ids = {
                record.id: record[inverse_name].id
                for record in records
                if record.id and record[inverse_name]
            }
            snapshots.append({
                **spec,
                'changed_fields': changed_fields,
                'old_values': self.capture_old_values(records, changed_fields),
                'parent_ids': parent_ids,
            })
        return snapshots

    # ─── Log helpers ─────────────────────────────────────────────────

    @api.model
    def log_changes(self, records, vals, old_snapshot, config, change_type='write'):
        """
        Diff old_snapshot vs new field values → post chatter + write log entries.
        """
        if not config:
            return

        tracked_fields = config.get_tracked_field_names()
        changed_fields = [f for f in tracked_fields if f in vals]

        if not changed_fields:
            return

        for record in records:
            if not record.exists():
                continue

            changes = []
            log_vals_list = []

            for fname in changed_fields:
                old_display = (old_snapshot or {}).get(record.id, {}).get(fname)
                try:
                    new_display = self._get_display_value(record, fname)
                except Exception:
                    continue

                if old_display == new_display:
                    continue

                field_obj = record._fields.get(fname)
                field_label = field_obj.string if field_obj else fname
                field_type  = field_obj.type   if field_obj else 'char'

                changes.append(self._format_change_row(field_label, old_display, new_display))

                log_vals_list.append({
                    'config_id':        config.id,
                    'model_name':       record._name,
                    'model_label':      record._description,
                    'record_id':        record.id,
                    'record_name':      record.display_name,
                    'field_name':       fname,
                    'field_label':      field_label,
                    'field_type':       field_type,
                    'old_value':        str(old_display) if old_display is not None else False,
                    'new_value':        str(new_display) if new_display is not None else False,
                    'changed_by':       self.env.uid,
                    'changed_by_name':  self.env.user.name,
                    'change_type':      change_type,
                })

            if not changes:
                continue

            # ── Chatter ──────────────────────────────────────────────
            if hasattr(record, 'message_post'):
                body = self._build_chatter_body(changes, change_type)
                try:
                    record.with_context(aft_skip_tracking=True).message_post(
                        body=Markup(body),
                        message_type='notification',
                        subtype_xmlid='mail.mt_comment' if config.notify_followers else 'mail.mt_note',
                    )
                except Exception as e:
                    _logger.warning('AFT chatter error %s #%s: %s', record._name, record.id, e)

            # ── DB log ───────────────────────────────────────────────
            if log_vals_list:
                try:
                    self.env['field.tracker.log'].sudo().with_context(aft_skip_tracking=True).create(log_vals_list)
                except Exception as e:
                    _logger.warning('AFT log write error: %s', e)

    @api.model
    def log_o2m_line_changes(self, records, snapshots):
        """Log child-line write diffs on the configured parent record chatter."""
        for snapshot in snapshots:
            config = snapshot['config']
            parent_model = self.env[config.model_name]
            inverse_name = snapshot['inverse_name']
            changed_fields = snapshot['changed_fields']

            for record in records:
                if not record.exists():
                    continue

                parent_id = snapshot['parent_ids'].get(record.id) or record[inverse_name].id
                parent = parent_model.browse(parent_id)
                if not parent.exists():
                    continue

                changes = []
                log_vals_list = []
                line_label = self._get_line_label(record)

                for fname in changed_fields:
                    old_display = (snapshot['old_values'] or {}).get(record.id, {}).get(fname)
                    try:
                        new_display = self._get_display_value(record, fname)
                    except Exception:
                        continue

                    if old_display == new_display:
                        continue

                    field_obj = record._fields.get(fname)
                    field_label = field_obj.string if field_obj else fname
                    field_type = field_obj.type if field_obj else 'char'
                    full_label = _('%(line_field)s / %(line)s / %(field)s') % {
                        'line_field': snapshot['o2m_field_label'],
                        'line': line_label,
                        'field': field_label,
                    }

                    changes.append(self._format_change_row(full_label, old_display, new_display))
                    log_vals_list.append({
                        'config_id':       config.id,
                        'model_name':      record._name,
                        'model_label':     record._description,
                        'record_id':       record.id,
                        'record_name':     '%s / %s' % (parent.display_name, line_label),
                        'field_name':      '%s.%s' % (snapshot['o2m_field_name'], fname),
                        'field_label':     full_label,
                        'field_type':      field_type,
                        'old_value':       str(old_display) if old_display is not None else False,
                        'new_value':       str(new_display) if new_display is not None else False,
                        'changed_by':      self.env.uid,
                        'changed_by_name': self.env.user.name,
                        'change_type':     'write',
                    })

                if not changes:
                    continue

                if hasattr(parent, 'message_post'):
                    body = self._build_chatter_body(changes, 'write')
                    try:
                        parent.with_context(aft_skip_tracking=True).message_post(
                            body=Markup(body),
                            message_type='notification',
                            subtype_xmlid='mail.mt_comment' if config.notify_followers else 'mail.mt_note',
                        )
                    except Exception as e:
                        _logger.warning('AFT O2M chatter error %s #%s: %s', parent._name, parent.id, e)

                if log_vals_list:
                    try:
                        self.env['field.tracker.log'].sudo().with_context(aft_skip_tracking=True).create(log_vals_list)
                    except Exception as e:
                        _logger.warning('AFT O2M log write error: %s', e)

    @api.model
    def log_o2m_line_creation(self, records):
        """Log newly created child lines on configured parent records."""
        for spec in self.get_parent_o2m_specs(records._name):
            config = spec['config']
            if not config or not config.log_on_create:
                continue
            inverse_name = spec['inverse_name']
            tracked_fields = self.get_trackable_field_names_for_model(records._name, inverse_name)
            parent_model = self.env[config.model_name]

            for record in records:
                parent = parent_model.browse(record[inverse_name].id)
                if not parent.exists():
                    continue

                changes = []
                log_vals_list = []
                line_label = self._get_line_label(record)
                for fname in tracked_fields:
                    try:
                        new_display = self._get_display_value(record, fname)
                    except Exception:
                        continue
                    if not new_display:
                        continue

                    field_obj = record._fields.get(fname)
                    field_label = field_obj.string if field_obj else fname
                    field_type = field_obj.type if field_obj else 'char'
                    full_label = _('%(line_field)s / %(line)s / %(field)s') % {
                        'line_field': spec['o2m_field_label'],
                        'line': line_label,
                        'field': field_label,
                    }

                    changes.append(self._format_change_row(full_label, '—', new_display))
                    log_vals_list.append({
                        'config_id':       config.id,
                        'model_name':      record._name,
                        'model_label':     record._description,
                        'record_id':       record.id,
                        'record_name':     '%s / %s' % (parent.display_name, line_label),
                        'field_name':      '%s.%s' % (spec['o2m_field_name'], fname),
                        'field_label':     full_label,
                        'field_type':      field_type,
                        'old_value':       False,
                        'new_value':       str(new_display),
                        'changed_by':      self.env.uid,
                        'changed_by_name': self.env.user.name,
                        'change_type':     'create',
                    })

                if not changes:
                    continue

                if hasattr(parent, 'message_post'):
                    body = self._build_chatter_body(changes, 'create')
                    try:
                        parent.with_context(aft_skip_tracking=True).message_post(
                            body=Markup(body),
                            message_type='notification',
                            subtype_xmlid='mail.mt_note',
                        )
                    except Exception as e:
                        _logger.warning('AFT O2M create chatter error %s #%s: %s', parent._name, parent.id, e)

                if log_vals_list:
                    try:
                        self.env['field.tracker.log'].sudo().with_context(aft_skip_tracking=True).create(log_vals_list)
                    except Exception as e:
                        _logger.warning('AFT O2M create log write error: %s', e)

    @api.model
    def log_o2m_line_deletion(self, records):
        """Log deleted child lines on configured parent records before unlink."""
        for spec in self.get_parent_o2m_specs(records._name):
            config = spec['config']
            if not config or not config.log_on_unlink:
                continue
            inverse_name = spec['inverse_name']
            parent_model = self.env[config.model_name]

            for record in records:
                parent = parent_model.browse(record[inverse_name].id)
                if not parent.exists():
                    continue

                line_label = self._get_line_label(record)
                full_label = _('%(line_field)s / %(line)s / Record') % {
                    'line_field': spec['o2m_field_label'],
                    'line': line_label,
                }
                changes = [self._format_change_row(full_label, line_label, 'DELETED')]
                if hasattr(parent, 'message_post'):
                    body = self._build_chatter_body(changes, 'unlink')
                    try:
                        parent.with_context(aft_skip_tracking=True).message_post(
                            body=Markup(body),
                            message_type='notification',
                            subtype_xmlid='mail.mt_note',
                        )
                    except Exception as e:
                        _logger.warning('AFT O2M delete chatter error %s #%s: %s', parent._name, parent.id, e)

                try:
                    self.env['field.tracker.log'].sudo().with_context(aft_skip_tracking=True).create({
                        'config_id':       config.id,
                        'model_name':      record._name,
                        'model_label':     record._description,
                        'record_id':       record.id,
                        'record_name':     '%s / %s' % (parent.display_name, line_label),
                        'field_name':      '%s.id' % spec['o2m_field_name'],
                        'field_label':     full_label,
                        'field_type':      'integer',
                        'old_value':       line_label,
                        'new_value':       'DELETED',
                        'changed_by':      self.env.uid,
                        'changed_by_name': self.env.user.name,
                        'change_type':     'unlink',
                    })
                except Exception as e:
                    _logger.warning('AFT O2M delete log write error: %s', e)

    @api.model
    def log_creation(self, records, config):
        if not config or not config.log_on_create:
            return

        tracked_fields = config.get_tracked_field_names()

        for record in records:
            changes = []
            log_vals_list = []

            for fname in tracked_fields:
                try:
                    val = self._get_display_value(record, fname)
                except Exception:
                    continue
                if not val:
                    continue

                field_obj = record._fields.get(fname)
                field_label = field_obj.string if field_obj else fname
                field_type  = field_obj.type   if field_obj else 'char'

                changes.append(self._format_change_row(field_label, '—', val))
                log_vals_list.append({
                    'config_id':       config.id,
                    'model_name':      record._name,
                    'model_label':     record._description,
                    'record_id':       record.id,
                    'record_name':     record.display_name,
                    'field_name':      fname,
                    'field_label':     field_label,
                    'field_type':      field_type,
                    'old_value':       False,
                    'new_value':       str(val),
                    'changed_by':      self.env.uid,
                    'changed_by_name': self.env.user.name,
                    'change_type':     'create',
                })

            if hasattr(record, 'message_post') and changes:
                body = self._build_chatter_body(changes, 'create')
                try:
                    record.with_context(aft_skip_tracking=True).message_post(
                        body=Markup(body),
                        message_type='notification',
                        subtype_xmlid='mail.mt_note',
                    )
                except Exception as e:
                    _logger.warning('AFT create chatter error %s #%s: %s', record._name, record.id, e)

            if log_vals_list:
                try:
                    self.env['field.tracker.log'].sudo().with_context(aft_skip_tracking=True).create(log_vals_list)
                except Exception as e:
                    _logger.warning('AFT create log write error: %s', e)

    @api.model
    def log_deletion(self, records, config):
        if not config or not config.log_on_unlink:
            return
        log_vals_list = []
        for record in records:
            log_vals_list.append({
                'config_id':       config.id,
                'model_name':      record._name,
                'model_label':     record._description,
                'record_id':       record.id,
                'record_name':     record.display_name,
                'field_name':      'id',
                'field_label':     'Record',
                'field_type':      'integer',
                'old_value':       record.display_name,
                'new_value':       'DELETED',
                'changed_by':      self.env.uid,
                'changed_by_name': self.env.user.name,
                'change_type':     'unlink',
            })
        if log_vals_list:
            try:
                self.env['field.tracker.log'].sudo().with_context(aft_skip_tracking=True).create(log_vals_list)
            except Exception as e:
                _logger.warning('AFT delete log write error: %s', e)

    # ─── Display value helper ────────────────────────────────────────

    def _get_display_value(self, record, fname):
        """Return human-readable string for any field value."""
        field_obj = record._fields.get(fname)
        if not field_obj:
            return None

        raw   = record[fname]
        ftype = field_obj.type

        if ftype == 'many2one':
            return raw.display_name if raw else False

        if ftype == 'selection':
            try:
                sel = field_obj.selection
                if callable(sel):
                    sel = sel(record)
                sel_dict = dict(sel)
                return sel_dict.get(raw, raw) if raw is not False else False
            except Exception:
                return str(raw) if raw is not False else False

        if ftype == 'boolean':
            return _('Yes') if raw else _('No')

        if ftype in ('date', 'datetime'):
            return str(raw) if raw else False

        if ftype in ('float', 'monetary'):
            return str(round(raw, 4)) if raw is not None else False

        if ftype == 'integer':
            return str(raw) if raw is not None else False

        return str(raw) if raw else False

    def _get_line_label(self, record):
        """Return a compact label for a child line record."""
        if 'product_id' in record._fields and record.product_id:
            return record.product_id.display_name
        return record.display_name or _('%(model)s #%(id)s') % {
            'model': record._description,
            'id': record.id,
        }

    # ─── HTML builders ───────────────────────────────────────────────

    def _format_change_row(self, field_label, old_val, new_val):
        def safe_value(value):
            return escape(value if value not in (False, None, '') else '—')

        field_html = escape(field_label or '')
        old_html = (f'<span style="color:#e74c3c;text-decoration:line-through">'
                    f'{safe_value(old_val)}</span>')
        new_html = (f'<span style="color:#27ae60;font-weight:600">'
                    f'{safe_value(new_val)}</span>')
        return (
            f'<tr>'
            f'<td style="padding:3px 8px;font-weight:600;color:#555">{field_html}</td>'
            f'<td style="padding:3px 8px">{old_html}</td>'
            f'<td style="padding:3px 8px;color:#999">→</td>'
            f'<td style="padding:3px 8px">{new_html}</td>'
            f'</tr>'
        )

    def _build_chatter_body(self, change_rows, change_type):
        icon  = {'create': '🟢', 'write': '✏️', 'unlink': '🔴'}.get(change_type, '📋')
        label = {
            'create': _('Record Created — Initial Values'),
            'write':  _('Field Changes'),
            'unlink': _('Record Deleted'),
        }.get(change_type, _('Field Changes'))

        rows_html = ''.join(change_rows)
        return f'''
<div style="font-family:sans-serif;font-size:13px">
  <div style="font-weight:700;margin-bottom:6px;color:#2c3e50">
    {icon} <strong>Auto Field Tracker</strong> — {label}
  </div>
  <table style="border-collapse:collapse;width:100%;max-width:600px;
                background:#f9f9f9;border:1px solid #ddd;border-radius:4px">
    <thead>
      <tr style="background:#eef2f7">
        <th style="padding:4px 8px;text-align:left;color:#666;font-size:12px">Field</th>
        <th style="padding:4px 8px;text-align:left;color:#666;font-size:12px">Before</th>
        <th style="padding:4px 8px"></th>
        <th style="padding:4px 8px;text-align:left;color:#666;font-size:12px">After</th>
      </tr>
    </thead>
    <tbody>{rows_html}</tbody>
  </table>
</div>
'''


# ════════════════════════════════════════════════════════════════════
# ORM HOOKS
#
# This must be a normal Odoo `_inherit = 'base'` extension. Patching
# `models.BaseModel` at import time is unreliable because many business
# models have their own create/write/unlink chain built by the registry.
# ════════════════════════════════════════════════════════════════════

_SKIP_MODELS = frozenset({
    'field.tracker.config',
    'field.tracker.log',
    'field.tracker.service',
    'field.tracker.mixin',
    'mail.message',
    'mail.notification',
    'mail.tracking.value',
    'mail.message.subtype',
    'bus.bus',
    'ir.model',
    'ir.model.fields',
    'ir.rule',
    'ir.property',
    'base.automation',
    'ir.attachment',
})


class AutoFieldTrackerBase(models.AbstractModel):
    _inherit = 'base'

    def _aft_should_skip_tracking(self):
        return (
            self.env.context.get('aft_skip_tracking')
            or self._name in _SKIP_MODELS
            or getattr(self, '_transient', False)
        )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if self._aft_should_skip_tracking():
            return records

        service = self.env['field.tracker.service']
        try:
            config = service.get_active_config(self._name)
            if config and config.log_on_create:
                service.log_creation(records, config)
        except Exception as e:
            _logger.warning('AFT create hook error on %s: %s', self._name, e)
        try:
            service.log_o2m_line_creation(records)
        except Exception as e:
            _logger.warning('AFT O2M create hook error on %s: %s', self._name, e)
        return records

    def write(self, vals):
        if self._aft_should_skip_tracking():
            return super().write(vals)

        old_snapshot = None
        config = None
        o2m_snapshots = []
        service = self.env['field.tracker.service']

        try:
            config = service.get_active_config(self._name)
            if config and config.log_on_write:
                tracked = config.get_tracked_field_names()
                changed = [fname for fname in tracked if fname in vals]
                if changed:
                    old_snapshot = service.capture_old_values(self, changed)
        except Exception as e:
            _logger.warning('AFT pre-write hook error on %s: %s', self._name, e)
        try:
            o2m_snapshots = service.prepare_o2m_write_tracking(self, vals)
        except Exception as e:
            _logger.warning('AFT O2M pre-write hook error on %s: %s', self._name, e)

        result = super().write(vals)

        if old_snapshot is not None and config:
            try:
                service.log_changes(self, vals, old_snapshot, config, 'write')
            except Exception as e:
                _logger.warning('AFT post-write hook error on %s: %s', self._name, e)
        if o2m_snapshots:
            try:
                service.log_o2m_line_changes(self, o2m_snapshots)
            except Exception as e:
                _logger.warning('AFT O2M post-write hook error on %s: %s', self._name, e)

        return result

    def unlink(self):
        if not self._aft_should_skip_tracking():
            service = self.env['field.tracker.service']
            try:
                config = service.get_active_config(self._name)
                if config and config.log_on_unlink:
                    service.log_deletion(self, config)
            except Exception as e:
                _logger.warning('AFT unlink hook error on %s: %s', self._name, e)
            try:
                service.log_o2m_line_deletion(self)
            except Exception as e:
                _logger.warning('AFT O2M unlink hook error on %s: %s', self._name, e)
        return super().unlink()
