# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SimplifyAccessTab(models.Model):
    """Notebook Tab/Page Access configuration line (Phase 6).

    Identifies a notebook <page> by its TECHNICAL name attribute (never
    by the translated page_string label - stored here only for display),
    optionally scoped to one specific view.
    """
    _name = 'simplify.access.tab'
    _description = 'Access Management Tab Rule'
    _order = 'model_name, page_name'

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
        help='Optional. Restrict this tab only on this specific view. '
             'Leave empty to hide the tab on ANY view of the selected '
             'model where a page with this technical name appears.',
    )

    page_name = fields.Char(
        string='Technical Page Name',
        required=True,
        help='The technical "name" attribute of the <page> XML node. '
             'If the target view has no stable technical name attribute '
             'on the page you want to hide, this rule cannot safely '
             'match it - matching by translated label alone is not '
             'supported, by design (labels are not stable identifiers).',
    )
    page_string = fields.Char(
        string='Page Label',
        help='Optional, informational only - the human-readable label '
             'of the page at the time this rule was configured. NOT '
             'used for matching.',
    )

    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        (
            'unique_tab_per_rule',
            'unique(access_rule_id, model_id, view_id, page_name)',
            'This tab is already configured in this access rule for '
            'this model/view.',
        ),
    ]

    @api.constrains('access_rule_id', 'model_id', 'view_id', 'page_name')
    def _check_unique_tab_per_rule(self):
        for line in self:
            duplicate = self.search([
                ('id', '!=', line.id),
                ('access_rule_id', '=', line.access_rule_id.id),
                ('model_id', '=', line.model_id.id),
                ('view_id', '=', line.view_id.id if line.view_id else False),
                ('page_name', '=', line.page_name),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'This tab is already configured in this access rule '
                    'for this model/view.'
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
