# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval

# ASSUMPTION FLAGGED FOR MANUAL VERIFICATION: odoo.tools.safe_eval has
# historically re-exported the standard library `time` module as a
# convenience for domain/expression authors. This was not verified
# against local Odoo 19 source, so it's imported defensively - if the
# re-export doesn't exist in this version, we simply fall back to the
# standard library's own `time` module directly, which is functionally
# identical for the purpose used here (a safe local variable available
# during save-time domain validation only).
try:
    from odoo.tools.safe_eval import time
except ImportError:
    import time

DOMAIN_HELP = (
    "Standard Odoo domain expression, e.g. [('user_id', '=', user.id)].\n\n"
    "Examples:\n"
    "  Current user:          [('user_id', '=', user.id)]\n"
    "  Current company:       [('company_id', '=', company.id)]\n"
    "  Allowed companies:     [('company_id', 'in', company_ids)]\n"
    "  Current user partner:  [('partner_id', '=', user.partner_id.id)]\n\n"
    "Available variables: user, uid, company, company_ids, time - these "
    "are provided by Simplify's OWN dynamic enforcement engine (see "
    "models/access_enforcement.py), evaluated fresh for the current "
    "request. This is independent of - and does not touch - native Odoo "
    "ir.rule in any way."
)


class SimplifyAccessDomain(models.Model):
    """Domain / record-level Access configuration line (Phase 5).

    ARCHITECTURE (revised)
    -----------------------
    This model is PURE CONFIGURATION - it stores what the restriction
    should be. It does NOT generate, modify, or depend on any native
    ``ir.rule`` record, and does NOT add any field to ``ir.rule`` or
    ``res.groups``. Native Odoo record rules remain completely
    independent and untouched.

    Enforcement is dynamic: the effective domain is resolved at request
    time by ``simplify.access.policy.get_domain_policy()`` and applied by
    the centralized enforcement layer in ``models/access_enforcement.py``
    (the same ``_inherit = 'base'`` class already used for Phases 2 and
    4), which ANDs it onto the incoming search domain / validates
    records against it on write, unlink and create - never by writing
    into native security tables.
    """
    _name = 'simplify.access.domain'
    _description = 'Access Management Domain Rule'
    _order = 'sequence, model_name, name'

    access_rule_id = fields.Many2one(
        comodel_name='simplify.access.rule',
        string='Access Rule',
        required=True,
        ondelete='cascade',
        index=True,
    )

    name = fields.Char(
        string='Name',
        required=True,
        help='Descriptive name, e.g. "Only My Leads".',
    )
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Inactive lines are ignored by the access engine.',
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

    domain_expression = fields.Text(
        string='Domain',
        required=True,
        default='[]',
        help=DOMAIN_HELP,
    )

    apply_read = fields.Boolean(
        string='Read',
        default=True,
        help='Restrict which records the targeted users can see/search.',
    )
    apply_write = fields.Boolean(
        string='Write',
        default=False,
        help='Restrict which records the targeted users can modify.',
    )
    apply_unlink = fields.Boolean(
        string='Delete',
        default=False,
        help='Restrict which records the targeted users can delete.',
    )
    apply_create = fields.Boolean(
        string='Create',
        default=False,
        help='Newly created records must satisfy this domain.',
    )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    @api.constrains('model_id')
    def _check_model_is_allowed(self):
        for line in self:
            if not line.model_id:
                continue
            if line.model_id.transient:
                raise ValidationError(_(
                    'Domain Access rules cannot target transient models '
                    '(wizards) such as "%(model)s" - this is disabled '
                    'by design in this phase to avoid breaking '
                    'legitimate wizard flows.',
                    model=line.model_id.model,
                ))
            if line.model_id.model in (
                'simplify.access.rule',
                'simplify.access.model',
                'simplify.access.menu',
                'simplify.access.field',
                'simplify.access.domain',
                'simplify.access.policy',
            ):
                raise ValidationError(_(
                    'Domain Access rules cannot target Simplify Access '
                    'Management\'s own configuration models, to avoid '
                    'the risk of locking administrators out of the '
                    'configuration screens.'
                ))

    @api.constrains('domain_expression', 'model_id')
    def _check_domain_expression(self):
        for line in self:
            if not line.model_id or not line.domain_expression:
                continue
            domain_value = line._simplify_safe_eval_domain()
            if not isinstance(domain_value, (list, tuple)):
                raise ValidationError(_(
                    'Invalid domain for model %(model)s: the expression '
                    'must evaluate to a list of conditions, e.g. '
                    '[("user_id", "=", user.id)].',
                    model=line.model_id.model,
                ))
            # Dry-run the domain through Odoo's own real domain parser,
            # via the standard public search() API - never an internal
            # or uncertain-signature method - so a malformed field name
            # or operator is caught with a clean message instead of a
            # raw traceback. sudo() is used only so validating a domain
            # never depends on the configuring manager's own access
            # rights to the target model.
            #
            # FIX: this previously passed count=True alongside limit=1,
            # which raised "BaseModel.search() got an unexpected keyword
            # argument 'count'" in this Odoo 19 environment - search()
            # no longer accepts a count= keyword here. limit=1 alone is
            # sufficient for validation purposes: it still forces Odoo to
            # parse and execute the domain against the real model (so a
            # malformed field/operator still raises the same clean
            # ValidationError below), while fetching at most a single
            # record's id - never all matching records, and never
            # requiring a genuine count. The result is discarded
            # immediately and never returned to any caller.
            try:
                line.env[line.model_id.model].sudo().search(
                    domain_value, limit=1,
                )
            except ValidationError:
                raise
            except Exception as exc:
                raise ValidationError(_(
                    'Invalid domain for model %(model)s: %(error)s',
                    model=line.model_id.model, error=str(exc),
                ))

    def _simplify_safe_eval_domain(self):
        """Parse domain_expression using odoo.tools.safe_eval with a
        tightly controlled context - no env, no request, no __import__,
        no filesystem access, no arbitrary builtins beyond what
        safe_eval itself already restricts.

        Used both for save-time validation (see
        _check_domain_expression above) AND at actual enforcement time
        by simplify.access.policy.get_domain_policy() - this is the
        single source of truth for evaluating a stored domain_expression,
        so there is exactly one context definition (user/uid/company/
        company_ids/time) used consistently everywhere, unlike the
        previous ir.rule-based design which risked a mismatch between
        this context and native ir.rule's own (different, unverified)
        one.
        """
        self.ensure_one()
        safe_context = {
            'user': self.env.user,
            'uid': self.env.uid,
            'company': self.env.company,
            'company_ids': self.env.companies.ids,
            'time': time,
        }
        try:
            return safe_eval(self.domain_expression, safe_context)
        except ValidationError:
            raise
        except Exception as exc:
            raise ValidationError(_(
                'Invalid domain expression: %(error)s', error=str(exc),
            ))

    # ------------------------------------------------------------------
    # CRUD - cache invalidation only, no native rule generation
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
