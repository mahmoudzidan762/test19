# -*- coding: utf-8 -*-
import logging

from lxml import etree

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class SimplifyAccessViewElementCandidate(models.TransientModel):
    """One discovered <button> or <page> element, shown to the
    administrator for selection.

    IMPORTANT ARCHITECTURE NOTE: this is a TransientModel whose rows are
    only ever referenced FROM another TransientModel (the picker wizard
    below) - never from a PERSISTENT config model. Odoo periodically
    vacuums (garbage-collects) transient records, so a persistent model
    must never hold a stored Many2one pointing at a transient row - that
    reference would eventually dangle. Both sides here are transient and
    share the same short-lived lifecycle, so this is safe. The actual
    persistent output of this whole flow is a plain technical-name Char
    value written onto simplify.access.button/simplify.access.tab (see
    action_add_selected() below) - never a reference to these candidate
    rows themselves.
    """
    _name = 'simplify.access.view.element.candidate'
    _description = 'Simplify Access Management - Discovered View Element (transient)'

    picker_id = fields.Many2one(
        comodel_name='simplify.access.view.element.picker',
        ondelete='cascade',
        required=True,
    )
    element_type = fields.Selection(
        selection=[('button', 'Button'), ('tab', 'Tab')],
        required=True,
    )
    # NOTE: these three are intentionally NOT marked readonly anywhere -
    # neither here at the model level, nor in the view
    # (views/access_view_element_picker_views.xml). They are only ever
    # populated via onchange (never typed by the user), and readonly=True
    # at EITHER the model level OR the view level was found to make the
    # web client drop these values from the actual create() payload when
    # the O2M candidate sub-record is persisted - even though onchange
    # set them correctly for on-screen display. This was the real cause
    # of "Technical Page Name (page_name) missing" downstream on
    # simplify.access.tab. action_add_selected() below also raises a
    # clear ValidationError if a technical identifier is still somehow
    # empty at creation time, as a safety net.
    technical_name = fields.Char(string='Technical Name')
    technical_type = fields.Char(string='Type')
    label = fields.Char(string='Label')
    selected = fields.Boolean(string='Add', default=False)


class SimplifyAccessViewElementPicker(models.TransientModel):
    """Discover selectable buttons/tabs from a view's real, final
    (fully inherited - base + module extensions + Studio, wherever
    technically resolvable) architecture, so administrators pick from
    what actually exists instead of typing technical XML identifiers
    from memory.

    Discovery is performed by calling THIS MODULE'S OWN, already-built
    and tested get_views() (Phase 4/6) with the internal bypass context
    set, so the wizard always sees the true native architecture -
    regardless of whether the configuring administrator happens to have
    any Simplify restrictions of their own applied elsewhere. This
    reuses the existing engine rather than building a second view
    resolution path, and needs no change to how get_views() itself
    already works.

    ASSUMPTION FLAGGED FOR MANUAL VERIFICATION: get_views() is called
    here as ``env[model].get_views([(view_id, view_type)], {})`` - a
    list of (id, type) tuples plus an options dict - which is the
    established calling convention this module has relied on (even if
    only as a callee, not previously as a caller) since Phase 4. This
    was not verified against local Odoo 19 source. If the exact call
    shape differs, discovery fails gracefully with a clear message (see
    _simplify_discover_view_elements below) rather than crashing the
    wizard or, worse, silently returning nothing.
    """
    _name = 'simplify.access.view.element.picker'
    _description = 'Simplify Access Management - Discover View Elements'

    access_rule_id = fields.Many2one(
        comodel_name='simplify.access.rule',
        required=True,
    )
    mode = fields.Selection(
        selection=[('button', 'Button'), ('tab', 'Tab')],
        required=True,
        default='button',
    )

    model_id = fields.Many2one(
        comodel_name='ir.model',
        string='Model',
        required=True,
    )
    model_name = fields.Char(
        related='model_id.model',
        string='Technical Model Name',
        store=False,
    )

    view_id = fields.Many2one(
        comodel_name='ir.ui.view',
        string='View',
        required=True,
        help='The specific view whose elements will be discovered. '
             'Only views belonging to the selected model are shown.',
    )

    candidate_ids = fields.One2many(
        comodel_name='simplify.access.view.element.candidate',
        inverse_name='picker_id',
        string='Discovered Elements',
    )

    @api.onchange('model_id')
    def _onchange_model_id(self):
        # Selecting a different model invalidates any previously chosen
        # view and discovered candidates - they belonged to the old
        # model's view.
        if self.view_id and self.model_id and self.view_id.model != self.model_id.model:
            self.view_id = False
        self.candidate_ids = [(5, 0, 0)]

    @api.onchange('view_id')
    def _onchange_view_id(self):
        self.candidate_ids = [(5, 0, 0)]
        if not self.view_id or not self.model_id:
            return
        try:
            items = self._simplify_discover_view_elements(
                self.model_id.model, self.view_id.id, self.mode,
            )
        except Exception as exc:
            _logger.warning(
                'simplify_access_management: view element discovery '
                'failed for model=%s view_id=%s mode=%s',
                self.model_id.model, self.view_id.id, self.mode,
                exc_info=True,
            )
            return {'warning': {
                'title': _('Discovery failed'),
                'message': _(
                    'Could not discover elements from this view: '
                    '%(error)s\n\nYou can still add a line manually on '
                    'the Buttons & Tabs tab if you know the exact '
                    'technical name.', error=str(exc),
                ),
            }}
        if not items:
            return {'warning': {
                'title': _('Nothing found'),
                'message': _(
                    'No %(kind)s elements with a technical name were '
                    'found on this view.',
                    kind=_('button') if self.mode == 'button' else _('tab'),
                ),
            }}
        self.candidate_ids = [
            (0, 0, {
                'element_type': self.mode,
                'technical_name': item['technical_name'],
                'technical_type': item['technical_type'],
                'label': item['label'],
            })
            for item in items
        ]

    def _simplify_discover_view_elements(self, model_name, view_id, mode):
        """Return a list of {'technical_name', 'technical_type', 'label'}
        dicts discovered from the FINAL, fully-resolved architecture of
        `view_id`, using this module's own get_views() (bypass context
        set, so Simplify's own hiding never interferes with discovery).

        Buttons: matched by <button name="..."> - type defaults to
        'object' when the type attribute is absent, matching Odoo's own
        default. Elements without a technical `name` attribute are
        skipped entirely (never offered) - matching by translated label
        alone is not supported anywhere in this module, by design.

        Tabs: matched by <page name="...">. A page with no `name`
        attribute cannot be safely/stably targeted and is skipped, for
        the same reason.
        """
        view = self.env['ir.ui.view'].sudo().browse(view_id)
        if not view.exists():
            raise UserError(_('The selected view no longer exists.'))
        view_type = view.type

        # SECURITY FIX (Phase 8 audit): this call previously used
        # with_context(simplify_access_bypass=True) WITHOUT .sudo() -
        # the one legitimate internal use of the bypass context that was
        # not paired with sudo() anywhere in the module. Since the
        # bypass-context-alone check has now been removed everywhere
        # (see models/access_enforcement.py's
        # _simplify_enforcement_skipped() docstring for the full
        # rationale), this call needed .sudo() added to continue
        # correctly showing the administrator the TRUE, unfiltered
        # architecture during discovery - consistent with every other
        # internal policy/config read in this module. This wizard is
        # itself only reachable by Access Management Managers (see
        # security/ir.model.access.csv), so elevating this one call is
        # safe and appropriate.
        result = self.env[model_name].sudo().with_context(
            simplify_access_bypass=True
        ).get_views([(view_id, view_type)], {})

        views_data = result.get('views') if isinstance(result, dict) else None
        view_data = (views_data or {}).get(view_type)
        arch = view_data.get('arch') if isinstance(view_data, dict) else None
        if not arch:
            raise UserError(_(
                'Could not retrieve the architecture for this view.'
            ))

        tree = etree.fromstring(
            arch.encode('utf-8') if isinstance(arch, str) else arch
        )

        items = []
        seen = set()
        tag = 'button' if mode == 'button' else 'page'
        for node in tree.iter(tag):
            name = node.get('name')
            if not name:
                continue
            if mode == 'button':
                technical_type = node.get('type') or 'object'
            else:
                technical_type = ''
            key = (name, technical_type)
            if key in seen:
                continue
            seen.add(key)
            label = node.get('string') or name
            items.append({
                'technical_name': name,
                'technical_type': technical_type,
                'label': label,
            })
        return items

    def action_add_selected(self):
        self.ensure_one()
        selected = self.candidate_ids.filtered('selected')
        if not selected:
            raise UserError(_('Select at least one element to add first.'))

        button_vals_list = []
        tab_vals_list = []

        for candidate in selected:
            technical_identifier = candidate.technical_name
            if not technical_identifier:
                raise ValidationError(_(
                    'The selected tab has no technical page name.'
                ) if candidate.element_type == 'tab' else _(
                    'The selected button has no technical name.'
                ))

            if candidate.element_type == 'button':
                button_vals_list.append({
                    'access_rule_id': self.access_rule_id.id,
                    'model_id': self.model_id.id,
                    'view_id': self.view_id.id,
                    'button_name': technical_identifier,
                    'button_type': candidate.technical_type or 'object',
                    'description': candidate.label,
                })
            elif candidate.element_type == 'tab':
                tab_vals_list.append({
                    'access_rule_id': self.access_rule_id.id,
                    'model_id': self.model_id.id,
                    'view_id': self.view_id.id,
                    'page_name': technical_identifier,
                    'page_string': candidate.label,
                    'active': True,
                })
            else:
                raise ValidationError(_(
                    'Unknown discovered element type: %(type)s',
                    type=candidate.element_type,
                ))

        if button_vals_list:
            self.env['simplify.access.button'].create(button_vals_list)
        if tab_vals_list:
            self.env['simplify.access.tab'].create(tab_vals_list)

        return {'type': 'ir.actions.act_window_close'}
