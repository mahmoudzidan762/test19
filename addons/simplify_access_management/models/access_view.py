# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

# NOTE: this list intentionally mirrors the commonly-available Odoo view
# types. "Only use types actually supported in the installed Odoo 19
# source" was requested, but this module has no local source access (see
# repeated assumption flags throughout this build). If a type below is
# not present/valid in your installation, selecting it simply never
# matches anything at enforcement time - it does not break installation,
# since this is a plain Selection field, not a foreign-key/registry
# lookup. Remove or add entries here if your Odoo 19 edition differs.
VIEW_TYPE_SELECTION = [
    ('form', 'Form'),
    ('list', 'List'),
    ('kanban', 'Kanban'),
    ('calendar', 'Calendar'),
    ('pivot', 'Pivot'),
    ('graph', 'Graph'),
    ('activity', 'Activity'),
    ('map', 'Map'),
    ('hierarchy', 'Hierarchy'),
    ('search', 'Search'),
]


class SimplifyAccessView(models.Model):
    """View Access configuration line (Phase 6).

    Restricts either:
      * one specific ir.ui.view record (view_id set), or
      * an entire view TYPE for a model (view_type set, view_id empty).

    At least one of the two must be set.
    """
    _name = 'simplify.access.view'
    _description = 'Access Management View Rule'
    _order = 'model_name, view_type'

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
        string='Specific View',
        ondelete='cascade',
        help='Restrict this exact view record. Leave empty to restrict '
             'by view TYPE instead (see below).',
    )
    view_type = fields.Selection(
        selection=VIEW_TYPE_SELECTION,
        string='View Type',
        help='Restrict this entire view type for the model (e.g. hide '
             'all Graph views for this model). Leave empty to restrict '
             'one specific view instead (see above).',
    )

    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        (
            'unique_view_per_rule',
            'unique(access_rule_id, model_id, view_id, view_type)',
            'This view/view type is already configured in this access '
            'rule.',
        ),
    ]

    @api.constrains('view_id', 'view_type')
    def _check_view_or_type_set(self):
        for line in self:
            if not line.view_id and not line.view_type:
                raise ValidationError(_(
                    'Select either a specific View or a View Type to '
                    'restrict.'
                ))

    @api.constrains('access_rule_id', 'model_id', 'view_id', 'view_type')
    def _check_unique_view_per_rule(self):
        for line in self:
            duplicate = self.search([
                ('id', '!=', line.id),
                ('access_rule_id', '=', line.access_rule_id.id),
                ('model_id', '=', line.model_id.id),
                ('view_id', '=', line.view_id.id if line.view_id else False),
                ('view_type', '=', line.view_type or False),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'This view/view type is already configured in this '
                    'access rule.'
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
