# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SimplifyAccessMenu(models.Model):
    """Menu Access configuration line (Phase 3).

    Each record belongs to exactly one simplify.access.rule and names ONE
    ir.ui.menu that must be hidden - purely from navigation/UI - for the
    users targeted by that rule, when the rule is applicable.

    IMPORTANT: this is UI/navigation visibility only. It is NOT a
    substitute for native Odoo ACL, native record rules, or the Phase 2
    model-level restrictions. Hiding a menu here does not, on its own,
    change what a user can do to the underlying model.
    """
    _name = 'simplify.access.menu'
    _description = 'Access Management Menu Rule'
    _order = 'id'

    access_rule_id = fields.Many2one(
        comodel_name='simplify.access.rule',
        string='Access Rule',
        required=True,
        ondelete='cascade',
        index=True,
    )

    menu_id = fields.Many2one(
        comodel_name='ir.ui.menu',
        string='Menu',
        required=True,
        ondelete='cascade',
        help='The menu (and, since hiding cascades to children, everything '
             'underneath it) to hide for the users targeted by this rule.',
    )
    menu_name = fields.Char(
        related='menu_id.complete_name',
        string='Complete Menu Path',
        readonly=True,
        store=False,
        help='Full breadcrumb-style path of the selected menu, e.g. '
             '"Sales / Orders / Quotations".',
    )

    _sql_constraints = [
        (
            'unique_menu_per_rule',
            'unique(access_rule_id, menu_id)',
            'The selected menu is already configured in this access rule.',
        ),
    ]

    @api.constrains('access_rule_id', 'menu_id')
    def _check_unique_menu_per_rule(self):
        # Belt-and-braces Python-level check in addition to the SQL
        # constraint above (same pattern as simplify.access.model in
        # Phase 2), so bulk/XML loads also raise a clean message.
        for line in self:
            duplicate = self.search([
                ('id', '!=', line.id),
                ('access_rule_id', '=', line.access_rule_id.id),
                ('menu_id', '=', line.menu_id.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'The selected menu is already configured in this '
                    'access rule.'
                ))

    # NOTE: same Odoo 19 create() signature assumption as documented in
    # models/access_enforcement.py - please verify against your local
    # source; a mismatch will fail loudly on module upgrade, not silently.
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._simplify_clear_menu_policy_cache()
        return records

    def write(self, vals):
        result = super().write(vals)
        self._simplify_clear_menu_policy_cache()
        return result

    def unlink(self):
        # Cache must be cleared for the rules these lines belonged to
        # BEFORE the rows disappear, otherwise nothing to key off - but
        # since the cache is keyed by (user_id, company_id) rather than by
        # rule/menu id, a full clear of this model's cache (not the whole
        # application's) after deletion is sufficient and correct.
        result = super().unlink()
        self.env['simplify.access.policy'].clear_caches()
        return result

    def _simplify_clear_menu_policy_cache(self):
        """Invalidate only the Simplify menu-visibility cache, not any
        other Odoo cache. Called after create/write of menu access lines
        so configuration changes take effect without requiring a full
        cache flush or server restart.
        """
        self.env['simplify.access.policy'].clear_caches()
