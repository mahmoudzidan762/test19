# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SimplifyAccessField(models.Model):
    """Field Access configuration line (Phase 4).

    Each record belongs to exactly one simplify.access.rule and describes
    dynamic, per-user field-level restrictions for ONE field of ONE model:
    invisible, readonly, required, remove_external_link, hide_export.

    IMPORTANT: field visibility/readonly/required here are dynamic and
    computed per-request for the current user - see
    models/access_enforcement.py::get_views(). Nothing in this model or
    its enforcement ever writes into ir.model.fields or
    ir.ui.view.arch_db; native view/field definitions are never modified.
    """
    _name = 'simplify.access.field'
    _description = 'Access Management Field Rule'
    _order = 'model_name, field_name'

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
        help='The Odoo model the selected field belongs to.',
    )
    model_name = fields.Char(
        related='model_id.model',
        string='Technical Model Name',
        store=True,
        readonly=True,
    )

    field_id = fields.Many2one(
        comodel_name='ir.model.fields',
        string='Field',
        required=True,
        ondelete='cascade',
        help='The field this restriction applies to. Must belong to the '
             'selected model.',
    )
    field_name = fields.Char(
        related='field_id.name',
        string='Technical Field Name',
        store=True,
        readonly=True,
    )
    field_description = fields.Char(
        related='field_id.field_description',
        string='Field Label',
        readonly=True,
        store=False,
    )

    invisible = fields.Boolean(
        string='Invisible',
        default=False,
        help='If enabled, this field is hidden from view for the users '
             'targeted by this rule.',
    )
    readonly = fields.Boolean(
        string='Read Only',
        default=False,
        help='If enabled, the users targeted by this rule can see this '
             'field but cannot modify it, in the UI and via direct RPC '
             'writes.',
    )
    required = fields.Boolean(
        string='Required',
        default=False,
        help='If enabled, the users targeted by this rule must provide a '
             'value for this field. Ignored automatically if this field '
             'is also effectively invisible for the same user, to avoid '
             'an impossible-to-complete form.',
    )
    remove_external_link = fields.Boolean(
        string='Remove External Link',
        default=False,
        help='For relational fields: removes the standard link to open '
             'the linked record, without affecting the user\'s access to '
             'the related model itself (configure that separately under '
             'Model Access if needed).',
    )
    hide_export = fields.Boolean(
        string='Hide From Export',
        default=False,
        help='If enabled, this field is removed from the export field '
             'picker and denied on direct export requests for the users '
             'targeted by this rule. Independent from "Invisible" - a '
             'field can be visible but not exportable, or invisible but '
             'still exportable.',
    )

    _sql_constraints = [
        (
            'unique_field_per_rule',
            'unique(access_rule_id, field_id)',
            'The selected field is already configured in this access '
            'rule.',
        ),
    ]

    @api.onchange('model_id')
    def _onchange_model_id(self):
        # If the model changes, drop a previously-selected field that no
        # longer belongs to it, rather than silently keeping a stale/
        # mismatched field_id around.
        if self.field_id and self.field_id.model_id != self.model_id:
            self.field_id = False

    @api.constrains('access_rule_id', 'field_id')
    def _check_unique_field_per_rule(self):
        # Belt-and-braces Python-level check in addition to the SQL
        # constraint above (same pattern as simplify.access.model /
        # simplify.access.menu), so bulk/XML loads also raise a clean
        # message.
        for line in self:
            duplicate = self.search([
                ('id', '!=', line.id),
                ('access_rule_id', '=', line.access_rule_id.id),
                ('field_id', '=', line.field_id.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'The selected field is already configured in this '
                    'access rule.'
                ))

    @api.constrains('model_id', 'field_id')
    def _check_field_belongs_to_model(self):
        # Defense in depth beyond the view-level domain (which is UI-only
        # and can be bypassed via direct RPC): the selected field must
        # actually belong to the selected model.
        for line in self:
            if line.field_id and line.model_id and line.field_id.model_id != line.model_id:
                raise ValidationError(_(
                    'The selected field "%(field)s" does not belong to '
                    'model "%(model)s".',
                    field=line.field_id.name, model=line.model_id.name,
                ))

    @api.constrains('invisible', 'required')
    def _check_invisible_required_conflict(self):
        # Phase 4 section 16: a single configuration line must never mark
        # the same field both Invisible and Required at once - that would
        # be an impossible form (the user cannot enter a value for a
        # field they cannot see). Cross-RULE conflicts (e.g. Rule A makes
        # a field invisible, Rule B makes the same field required) are a
        # separate, allowed case handled by normalization in the policy
        # engine (see simplify.access.policy.get_field_policy(): invisible
        # always suppresses required in the EFFECTIVE combined policy),
        # since we cannot retroactively forbid saving one rule just
        # because another, independently valid rule exists.
        for line in self:
            if line.invisible and line.required:
                raise ValidationError(_(
                    'Field "%(field)s": a field cannot be both Invisible '
                    'and Required on the same access rule line - this '
                    'would make the form impossible to complete.',
                    field=line.field_id.name or '',
                ))

    # ------------------------------------------------------------------
    # Cache invalidation
    # ------------------------------------------------------------------
    # NOTE: same Odoo 19 create() signature assumption as documented in
    # models/access_enforcement.py - please verify against your local
    # source; a mismatch will fail loudly on module upgrade, not silently.
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
