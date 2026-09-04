# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

BUTTON_TYPE_SELECTION = [
    ('object', 'Object (calls a Python method)'),
    ('action', 'Action (calls an ir.actions.* record)'),
]


class SimplifyAccessButton(models.Model):
    """Button Access configuration line (Phase 6).

    Identifies a button by its TECHNICAL name/type (never by translated
    label - labels are not stable identifiers) and optionally scopes it
    to one specific view. If view_id is not set, the restriction applies
    to any view of the selected model where a button with this name/type
    appears.
    """
    _name = 'simplify.access.button'
    _description = 'Access Management Button Rule'
    _order = 'model_name, button_name'

    access_rule_id = fields.Many2one(
        comodel_name='simplify.access.rule',
        string='Access Rule',
        required=True,
        ondelete='cascade',
        index=True,
    )

    model_id = fields.Many2one(
        comodel_name='ir.model',
        string='Model',
        required=True,
        ondelete='cascade',
    )
    model_name = fields.Char(
        related='model_id.model',
        string='Technical Model Name',
        store=True,
        readonly=True,
    )

    view_id = fields.Many2one(
        comodel_name='ir.ui.view',
        string='View',
        ondelete='cascade',
        help='Optional. Restrict this button only on this specific view. '
             'Leave empty to hide the button on ANY view of the selected '
             'model where it appears.',
    )

    button_name = fields.Char(
        string='Button Technical Name',
        required=True,
        help='The technical "name" attribute of the <button> XML node, '
             'e.g. "action_confirm". Never the translated label.',
    )
    button_type = fields.Selection(
        selection=BUTTON_TYPE_SELECTION,
        string='Type',
        required=True,
        default='object',
        help='The technical "type" attribute of the <button> XML node.',
    )

    description = fields.Char(string='Description')
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        (
            'unique_button_per_rule',
            'unique(access_rule_id, model_id, view_id, button_name, button_type)',
            'This button is already configured in this access rule for '
            'this model/view.',
        ),
    ]

    @api.constrains('access_rule_id', 'model_id', 'view_id', 'button_name', 'button_type')
    def _check_unique_button_per_rule(self):
        for line in self:
            duplicate = self.search([
                ('id', '!=', line.id),
                ('access_rule_id', '=', line.access_rule_id.id),
                ('model_id', '=', line.model_id.id),
                ('view_id', '=', line.view_id.id if line.view_id else False),
                ('button_name', '=', line.button_name),
                ('button_type', '=', line.button_type),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'This button is already configured in this access '
                    'rule for this model/view.'
                ))

    @api.constrains('model_id', 'view_id')
    def _check_view_matches_model(self):
        for line in self:
            if line.view_id and line.view_id.model and line.model_id \
                    and line.view_id.model != line.model_id.model:
                raise ValidationError(_(
                    'The selected view "%(view)s" does not belong to '
                    'model "%(model)s".',
                    view=line.view_id.name, model=line.model_id.model,
                ))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env['simplify.access.policy'].clear_caches()
        return records

    def write(self, vals):
        result = super().write(vals)
        self.env['simplify.access.policy'].clear_caches()
        return result

    def unlink(self):
        result = super().unlink()
        self.env['simplify.access.policy'].clear_caches()
        return result
