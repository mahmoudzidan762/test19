# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SimplifyAccessModel(models.Model):
    """Model Access configuration line.

    Each record belongs to exactly one simplify.access.rule and describes
    the restrictions that apply to ONE target model when that rule is
    applicable to the current user/company.

    Phase 2 scope: readonly / restrict_create / restrict_write /
    restrict_unlink only. UI hide_* flags (archive, duplicate, import,
    export, ...) are intentionally NOT implemented in this phase - they
    belong to later phases and must not be treated as security.
    """
    _name = 'simplify.access.model'
    _description = 'Access Management Model Rule'
    _order = 'model_name'

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
        help='The Odoo model this restriction applies to.',
    )
    model_name = fields.Char(
        related='model_id.model',
        string='Technical Model Name',
        store=True,
        readonly=True,
    )

    readonly = fields.Boolean(
        string='Read Only',
        default=False,
        help='If enabled, users targeted by this rule cannot create, '
             'modify or delete records of this model. Overrides the '
             'individual restrict_* flags below for this model line.',
    )
    restrict_create = fields.Boolean(
        string='Restrict Create',
        default=False,
        help='If enabled, users targeted by this rule cannot create new '
             'records of this model.',
    )
    restrict_write = fields.Boolean(
        string='Restrict Write',
        default=False,
        help='If enabled, users targeted by this rule cannot modify '
             'existing records of this model.',
    )
    restrict_unlink = fields.Boolean(
        string='Restrict Delete',
        default=False,
        help='If enabled, users targeted by this rule cannot delete '
             'records of this model.',
    )

    # UI-only flags - stored for future phases, NOT enforced yet.
    hide_archive = fields.Boolean(string='Hide Archive')
    hide_unarchive = fields.Boolean(string='Hide Unarchive')
    hide_duplicate = fields.Boolean(string='Hide Duplicate')
    hide_import = fields.Boolean(string='Hide Import')
    hide_export = fields.Boolean(string='Hide Export')

    _sql_constraints = [
        (
            'unique_model_per_rule',
            'unique(access_rule_id, model_id)',
            'The selected model is already configured in this access rule.',
        ),
    ]

    @api.constrains('access_rule_id', 'model_id')
    def _check_unique_model_per_rule(self):
        # Belt-and-braces Python-level check in addition to the SQL
        # constraint above, so the error is raised cleanly even in edge
        # cases (e.g. bulk XML data loads) where the SQL constraint
        # message might not surface as clearly.
        for line in self:
            duplicate = self.search([
                ('id', '!=', line.id),
                ('access_rule_id', '=', line.access_rule_id.id),
                ('model_id', '=', line.model_id.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'The selected model is already configured in this '
                    'access rule.'
                ))

    # ------------------------------------------------------------------
    # Cache invalidation
    # ------------------------------------------------------------------
    # Model Access lines feed into get_model_policy(), which is not
    # currently ormcache-decorated (Phase 2 has no cached method), so
    # there is technically nothing to invalidate for that method today.
    # These calls are added for architectural consistency with
    # simplify.access.rule and simplify.access.menu, and so that if a
    # future phase adds caching to get_model_policy(), it is already
    # correctly invalidated without further changes here. All three
    # configuration models call the same single central method.
    #
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
