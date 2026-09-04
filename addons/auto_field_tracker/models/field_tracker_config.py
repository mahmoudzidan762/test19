# -*- coding: utf-8 -*-

from markupsafe import Markup

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class FieldTrackerConfig(models.Model):
    """
    Configuration model that defines which fields on which models
    should be auto-tracked in the chatter.
    """
    _name = 'field.tracker.config'
    _description = 'Auto Field Tracker Configuration'
    _order = 'model_id, sequence'

    # ─── Config Identity ────────────────────────────────────────────
    name = fields.Char(
        string='Config Name',
        compute='_compute_name',
        store=True,
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help='When disabled, this config is paused but not deleted.',
    )
    sequence = fields.Integer(string='Sequence', default=10)

    # ─── Target Model ───────────────────────────────────────────────
    model_id = fields.Many2one(
        'ir.model',
        string='Model',
        required=True,
        ondelete='cascade',
        domain=[('transient', '=', False)],
        help='The Odoo model on which tracking will be applied.',
    )
    model_name = fields.Char(
        related='model_id.model',
        string='Model Technical Name',
        store=True,
        readonly=True,
    )
    model_has_chatter = fields.Boolean(
        string='Has Chatter?',
        compute='_compute_model_has_chatter',
        help='Only models inheriting mail.thread support chatter logging.',
    )

    # ─── Field Selection ────────────────────────────────────────────
    track_all_fields = fields.Boolean(
        string='Track ALL Fields',
        default=False,
        help='If enabled, ALL storable fields on this model will be tracked automatically.',
    )
    field_ids = fields.Many2many(
        'ir.model.fields',
        'field_tracker_config_fields_rel',
        'config_id',
        'field_id',
        string='Fields to Track',
        domain="[('model_id', '=', model_id), "
               "('ttype', 'not in', ['one2many', 'many2many', 'binary']), "
               "('store', '=', True), ('related', '=', False)]",
        help='Select which specific fields to track. Leave empty and enable '
             '"Track ALL Fields" to auto-track all storable fields.',
    )

    # ─── Logging Options ────────────────────────────────────────────
    log_on_create = fields.Boolean(
        string='Log on Record Creation',
        default=True,
        help='Log initial values when a new record is created.',
    )
    log_on_write = fields.Boolean(
        string='Log on Update',
        default=True,
        help='Log field changes whenever a record is updated.',
    )
    log_on_unlink = fields.Boolean(
        string='Log on Delete',
        default=False,
        help='Log a note when a record is deleted.',
    )
    notify_followers = fields.Boolean(
        string='Notify Followers',
        default=False,
        help='Send email notification to followers when tracked fields change.',
    )

    # ─── One2many Line Tracking ─────────────────────────────────────
    track_o2m_lines = fields.Boolean(
        string='Track One2many Lines',
        default=False,
        help='Also track changes to child line records and log them on the parent.',
    )
    o2m_field_ids = fields.Many2many(
        'ir.model.fields',
        'field_tracker_config_o2m_rel',
        'config_id',
        'field_id',
        string='One2many Fields to Track',
        domain="[('model_id', '=', model_id), ('ttype', '=', 'one2many')]",
    )

    # ─── Statistics ─────────────────────────────────────────────────
    log_count = fields.Integer(
        string='Total Log Entries',
        compute='_compute_log_count',
    )

    # ─── Computed Methods ───────────────────────────────────────────
    @api.depends('model_id', 'field_ids')
    def _compute_name(self):
        for rec in self:
            if rec.model_id:
                rec.name = f'Tracker: {rec.model_id.name}'
            else:
                rec.name = 'New Tracker Config'

    @api.depends('model_id')
    def _compute_model_has_chatter(self):
        for rec in self:
            if rec.model_id and rec.model_id.model:
                try:
                    if 'is_mail_thread' in rec.model_id._fields:
                        rec.model_has_chatter = bool(rec.model_id.is_mail_thread)
                    else:
                        rec.model_has_chatter = hasattr(self.env[rec.model_id.model], 'message_post')
                except Exception:
                    rec.model_has_chatter = False
            else:
                rec.model_has_chatter = False

    def _compute_log_count(self):
        for rec in self:
            rec.log_count = self.env['field.tracker.log'].search_count([
                ('config_id', '=', rec.id)
            ])

    # ─── Constraints ────────────────────────────────────────────────
    _sql_constraints = [
        ('unique_model_config', 'UNIQUE(model_id)',
         'A tracker configuration already exists for this model. '
         'Please edit the existing configuration.')
    ]

    @api.constrains('model_id')
    def _check_model_has_chatter(self):
        for rec in self:
            try:
                self.env[rec.model_id.model]
            except KeyError:
                raise ValidationError(_(
                    'Model "%s" is not available in the current environment.'
                ) % rec.model_id.name)

    # ─── Actions ────────────────────────────────────────────────────
    def action_view_logs(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Field Change Logs — %s') % self.model_id.name,
            'res_model': 'field.tracker.log',
            'view_mode': 'list,form',
            'domain': [('config_id', '=', self.id)],
            'context': {'default_config_id': self.id},
        }

    def action_test_tracking(self):
        """Quick-test button: logs a test message on the first record of the model."""
        self.ensure_one()
        records = self.env[self.model_id.model].search([], limit=1)
        if not records:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Records Found'),
                    'message': _('There are no records in model "%s" to test on.') % self.model_id.name,
                    'type': 'warning',
                }
            }
        records.message_post(
            body=Markup(_('🔍 <strong>Auto Field Tracker</strong>: Test log from tracker config.')),
            message_type='notification',
            subtype_xmlid='mail.mt_note',
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Test Successful'),
                'message': _('Test log posted on the first record of "%s".') % self.model_id.name,
                'type': 'success',
            }
        }

    # ─── Helper ─────────────────────────────────────────────────────
    def get_tracked_field_names(self):
        """
        Return list of field names to track for this config.
        If track_all_fields is True, return all storable, non-relational fields.
        """
        self.ensure_one()
        model_cls = self.env[self.model_id.model]

        if self.track_all_fields:
            skip_types = {'one2many', 'many2many', 'binary'}
            skip_names = {
                'id', 'create_uid', 'create_date', 'write_uid', 'write_date',
                '__last_update', 'message_ids', 'message_follower_ids',
                'activity_ids', 'message_is_follower', 'message_needaction',
                'message_needaction_counter', 'activity_state',
            }
            return [
                name for name, field in model_cls._fields.items()
                if field.type not in skip_types
                and name not in skip_names
                and getattr(field, 'store', True)
                and not getattr(field, 'related', None)
                and not (getattr(field, 'compute', None) and getattr(field, 'readonly', False))
            ]
        else:
            return [f.name for f in self.field_ids]


class FieldTrackerConfigLine(models.Model):
    """
    Extends ir.model to show the active tracker config from the model list.
    """
    _inherit = 'ir.model'

    tracker_config_id = fields.Many2one(
        'field.tracker.config',
        string='Tracker Config',
        compute='_compute_tracker_config',
    )
    has_tracker = fields.Boolean(
        string='Has Tracker',
        compute='_compute_tracker_config',
    )

    def _compute_tracker_config(self):
        for rec in self:
            config = self.env['field.tracker.config'].search([
                ('model_id', '=', rec.id), ('active', '=', True)
            ], limit=1)
            rec.tracker_config_id = config
            rec.has_tracker = bool(config)
