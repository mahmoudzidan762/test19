# -*- coding: utf-8 -*-
import ast
import logging

from lxml import etree

from odoo import _, api, models
from odoo.exceptions import AccessError, ValidationError
from odoo.osv import expression

from .access_policy import SIMPLIFY_ACCESS_BYPASS_KEY

_logger = logging.getLogger(__name__)


class Base(models.AbstractModel):
    """Extend every Odoo model with Simplify Access Management's model-level
    (Phase 2) and field-level (Phase 4) enforcement.

    Architecture note
    ------------------
    ``_inherit = 'base'`` is the standard, supported Odoo extension point
    for adding cross-model behaviour to every model in the registry
    (Odoo's own ``mail`` and other core addons use the same technique).
    This is normal Odoo inheritance, NOT monkey patching: no Python class
    or method is being patched in place, and no Odoo core file is
    modified.

    This override only ever ADDS restrictions on top of native Odoo
    security (ir.model.access, ir.rule, field-level groups, ...), which
    always remains authoritative and is evaluated first by the ORM before
    this code ever runs. If native Odoo already denies an operation, this
    override never even gets a chance to run more restrictively - it can
    only narrow further, never widen, native permissions.

    Recursion / self-exemption
    ---------------------------
    Every check below is bypass-context-tagged and uses sudo() to reach
    the policy helper and Simplify's own configuration models. Those
    configuration models are therefore never restricted by policies
    derived from themselves.

    TransientModel safety
    ----------------------
    Restrictions are skipped entirely for transient models (wizards) using
    the model's own ``_transient`` metadata flag, so legitimate wizard
    flows for a readonly-restricted user are never broken.

    Phase 4 addition
    -----------------
    Field-level checks (readonly write protection, required validation,
    export protection, and dynamic view-arch modifiers for
    invisible/readonly/required/remove_external_link) are added to this
    SAME central class, per the explicit Phase 4 instruction to extend
    the existing Phase 2 enforcement architecture rather than create a
    second, independent BaseModel enforcement layer.

    Phase 5 addition
    -----------------
    Record-level (domain) checks are added to this SAME central class
    too. Unlike Phases 2 and 4, Phase 5 does NOT generate, write to, or
    depend on any native security record (no ir.rule, no res.groups
    field) - it purely ANDs a dynamically-resolved domain onto the
    incoming search domain (via a minimal, maximally signature-tolerant
    _search() override) and validates records against the effective
    domain on write/unlink (before the operation) and create (after, in
    the same transaction). Native ir.model.access and ir.rule remain
    fully independent and authoritative throughout.
    """
    _inherit = 'base'

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _simplify_is_exempt_model(self):
        """Models that must never be subject to Simplify restrictions,
        regardless of any configured rule:

        * TransientModels (wizards) - explicitly required to keep working.
        * Simplify's own configuration models - avoids the engine locking
          administrators out of configuring itself, and avoids recursion
          when the policy resolver itself reads these models.

        NOTE: ``simplify.access.menu`` (Phase 3) and ``simplify.access.
        field`` (Phase 4) were added to this list now; they were missing
        from the Phase 2/3 version of this tuple, which - while never
        actually reachable by a non-bypass user in practice, since
        ir.model.access.csv already restricts those models to Access
        Management Managers, who bypass via _is_bypass_user() anyway -
        is fixed here for defense-in-depth and architectural consistency.
        """
        if self._transient:
            return True
        if self._name in (
            'simplify.access.rule',
            'simplify.access.model',
            'simplify.access.menu',
            'simplify.access.field',
            'simplify.access.domain',
            'simplify.access.button',
            'simplify.access.tab',
            'simplify.access.view',
            'simplify.access.action',
            'simplify.access.report',
            'simplify.access.view.element.picker',
            'simplify.access.view.element.candidate',
            'simplify.access.policy',
        ):
            return True
        return False

    def _simplify_get_model_policy(self):
        """Resolve the effective Phase 2 model policy for self._name,
        for the current user/company, using the internal bypass context
        so this lookup itself is never blocked by the very restrictions
        it is computing.
        """
        policy_helper = self.env['simplify.access.policy'].sudo().with_context(
            **{SIMPLIFY_ACCESS_BYPASS_KEY: True}
        )
        return policy_helper.get_model_policy(
            self._name, user=self.env.user, company=self.env.company,
        )

    def _simplify_get_field_policy(self):
        """Resolve the effective Phase 4 field policy dict for self._name,
        for the current user/company - see
        simplify.access.policy.get_field_policy() for the normalized
        shape. Same bypass-context/sudo() recursion guard as
        ``_simplify_get_model_policy``.
        """
        policy_helper = self.env['simplify.access.policy'].sudo().with_context(
            **{SIMPLIFY_ACCESS_BYPASS_KEY: True}
        )
        return policy_helper.get_field_policy(
            self._name, user=self.env.user, company=self.env.company,
        )

    def _simplify_get_global_policy(self):
        """Resolve the effective Phase 7 global/chatter policy dict for
        the current user/company - not scoped to self._name, since
        these are global restrictions by definition. Same bypass-
        context/sudo() recursion guard as the other policy helpers.
        """
        policy_helper = self.env['simplify.access.policy'].sudo().with_context(
            **{SIMPLIFY_ACCESS_BYPASS_KEY: True}
        )
        return policy_helper.get_global_policy(
            user=self.env.user, company=self.env.company,
        )

    def _simplify_get_model_description(self):
        """Human-readable model name for error messages. Shared by both
        the Phase 2 model-access checks and the Phase 4 field-access
        checks, to avoid duplicating this lookup (see Phase 4 section 28:
        keep the architecture centralized).
        """
        return self.env['ir.model']._get(self._name).name or self._name

    def _simplify_get_field_description(self, field_name):
        """Human-readable field label for error messages, looked up via
        ir.model.fields (sudo() + bypass context - this is metadata
        lookup, not a restricted business read).
        """
        field_record = self.env['ir.model.fields'].sudo().with_context(
            **{SIMPLIFY_ACCESS_BYPASS_KEY: True}
        ).search([
            ('model', '=', self._name),
            ('name', '=', field_name),
        ], limit=1)
        return field_record.field_description if field_record else field_name

    # Deliberately SHORT and JUSTIFIED - NOT a giant arbitrary whitelist
    # (Phase 7 bug fix section 3/4/5). Applies ONLY to the Phase 7
    # global_readonly flag, never to Phase 2's per-model restrict_create/
    # write/unlink - an administrator who deliberately configures a
    # Model Access restriction on any of these models (e.g. explicitly
    # restricting res.users writes) still has that fully respected.
    #
    # * res.users - but ONLY exempted when the write targets exclusively
    #   the CURRENT user's own record (checked in the method below, not
    #   here) - ordinary self-service preference changes (language,
    #   timezone, notification settings, sidebar/UI state, etc.) are not
    #   "business records" in the sense Global Read Only is meant to
    #   restrict, and a user must always be able to manage their own
    #   account preferences while using the web client normally. Editing
    #   ANY OTHER user's res.users record is a meaningful administrative
    #   action and is NOT exempted - it still goes through the normal
    #   restriction, so this is not a broad privilege bypass.
    # * res.users.settings - a technical, always-per-user settings
    #   record (Discuss/UI sync preferences etc.) Odoo writes to
    #   automatically as part of ordinary client/session behaviour, not
    #   business data by any reasonable definition. Exempted wholesale
    #   (not self-only) since there is no meaningful "someone else's
    #   settings" business-security concern for this model.
    # * bus.presence / mail.presence - online/presence heartbeat records
    #   updated automatically and frequently by the web client's normal
    #   polling behaviour; pure per-user technical status, not business
    #   data. Both names are checked defensively since the exact
    #   technical model name for this has varied across Odoo versions
    #   and was not verified against local Odoo 19 source.
    # * bus.bus - the notification/longpolling transport bus itself;
    #   pure technical message dispatch infrastructure, never business
    #   data under any definition, so a wholesale exemption carries no
    #   meaningful security risk.
    # * mail.notification - per-recipient message delivery/read-state
    #   tracking (e.g. marking one's own inbox notification as read);
    #   technical delivery metadata, not user-authored business content
    #   (the actual message content lives on mail.message/mail.thread,
    #   which remain fully subject to Global Read Only - this exemption
    #   is narrowly about the delivery-tracking row, not message
    #   content).
    #
    # NOTE: I could not verify the EXACT model(s) that caused the
    # originally-reported HTTP 500 without runtime/server access - this
    # list reflects my best-justified assessment of Odoo 19's known
    # technical/session infrastructure. If a crash recurs, please share
    # the specific model name from the server traceback so it can be
    # added here with full confidence instead of guessed.
    _GLOBAL_READONLY_SELF_ONLY_MODELS = frozenset({'res.users'})
    _GLOBAL_READONLY_ALWAYS_EXEMPT_MODELS = frozenset({
        'bus.presence', 'mail.presence', 'bus.bus',
        'res.users.settings', 'mail.notification',
    })

    def _simplify_is_global_readonly_exempt_model(self):
        """True if self._name/self should be exempt from Phase 7's
        global_readonly flag specifically - see the class-level comment
        above for the short, justified list and the reasoning behind
        each entry.
        """
        if self._name in self._GLOBAL_READONLY_ALWAYS_EXEMPT_MODELS:
            return True
        if self._name in self._GLOBAL_READONLY_SELF_ONLY_MODELS:
            # Only exempt when every record being touched IS the
            # current user's own res.users record - editing ANY OTHER
            # user's record still goes through the normal restriction.
            return bool(self) and set(self.ids) == {self.env.uid}
        return False

    def _simplify_check_model_access(self, operation):
        """Raise AccessError if the current user is restricted from
        performing `operation` ('create', 'write' or 'unlink') on
        self._name, per the effective Phase 2 model policy OR Phase 7's
        global_readonly flag (which behaves exactly like restrict_create
        + restrict_write + restrict_unlink all being True, for every
        non-exempt persistent model at once).

        Does nothing (no-op) for exempt models - see
        ``_simplify_is_exempt_model()`` - which already covers
        TransientModels/wizards using the model's own native
        ``_transient`` metadata flag (not a hardcoded name list), so
        global_readonly can never block legitimate wizard/dialog
        operations (Phase 7 section 3/8).

        FIX (previous HTTP 500 during login): this method previously
        never checked ``self.env.su``, unlike every Phase 5+ check in
        this class. The env.su check below covers internal/technical
        writes performed via sudo() by Odoo's own framework.

        FAIL-OPEN SCOPE (Phase 7 section 10 - intentionally narrow,
        NOT a broad security bypass): ONLY the policy RESOLUTION calls
        just below are wrapped - if resolving Phase 2/Phase 7 policy
        itself raises a genuine, unexpected error, this request is
        treated as unrestricted and the error is logged at ERROR level
        (loud and visible in server logs - never hidden, per section 9)
        rather than propagating into an HTTP 500 that could turn into a
        site-wide outage with no way for an administrator to log in and
        fix the misconfiguration. This does NOT weaken the actual
        enforcement decision once policy is successfully resolved - a
        correctly-resolved restriction is always enforced exactly as
        before. This fail-open is deliberately scoped to THIS method
        only (create/write/unlink model-level checks); Phase 4/5/6's own
        policy lookups are untouched, per the instruction to only fix
        Global Read Only in this round.

        SECURITY FIX (Phase 8 audit): the bypass-context-alone check
        that used to sit here was a critical vulnerability - see
        _simplify_enforcement_skipped()'s docstring for the full
        explanation. Replaced with a self.env.su check, which correctly
        and safely covers every legitimate internal use case (every
        internal policy read in this module pairs .sudo() with this
        context key) while being un-spoofable by an external RPC caller.
        """
        if self.env.su:
            return
        if self._simplify_is_exempt_model():
            return

        try:
            policy = self._simplify_get_model_policy()
            global_policy = self._simplify_get_global_policy()
        except Exception:
            _logger.error(
                'simplify_access_management: CRITICAL - failed to '
                'resolve Simplify access policy for model %s '
                '(operation=%s); treating THIS REQUEST ONLY as '
                'unrestricted to avoid a site-wide outage. This is a '
                'bug in the policy engine and must be investigated - '
                'restrictions are NOT being enforced for this model '
                'while this recurs.', self._name, operation, exc_info=True,
            )
            return

        flag_map = {
            'create': 'restrict_create',
            'write': 'restrict_write',
            'unlink': 'restrict_unlink',
        }
        flag = flag_map[operation]

        per_model_restricted = bool(policy.get(flag))
        globally_restricted = bool(global_policy.get('global_readonly'))
        if globally_restricted and self._simplify_is_global_readonly_exempt_model():
            globally_restricted = False

        if not (per_model_restricted or globally_restricted):
            return

        if globally_restricted:
            # Distinct wording for a global_readonly denial (Phase 7
            # section 7), separate from the Phase 2 per-model messages
            # below - a global_readonly user is not restricted from one
            # specific model, they are read-only everywhere.
            global_messages = {
                'create': _(
                    'Your access is read-only. You cannot create '
                    'records.'
                ),
                'write': _(
                    'Your access is read-only. You cannot modify '
                    'records.'
                ),
                'unlink': _(
                    'Your access is read-only. You cannot delete '
                    'records.'
                ),
            }
            raise AccessError(global_messages[operation])

        model_description = self._simplify_get_model_description()
        messages = {
            'create': _(
                'You are not allowed to create records of %(model)s.',
                model=model_description,
            ),
            'write': _(
                'You are not allowed to modify records of %(model)s.',
                model=model_description,
            ),
            'unlink': _(
                'You are not allowed to delete records of %(model)s.',
                model=model_description,
            ),
        }
        raise AccessError(messages[operation])

    # ------------------------------------------------------------------
    # Phase 4 - Field-level checks
    # ------------------------------------------------------------------
    def _simplify_check_field_write_access(self, vals):
        """Raise AccessError if `vals` attempts to write to any field that
        is marked readonly by the effective Phase 4 field policy.

        Only the fields actually present in `vals` are checked - an
        unrelated write to a different, unrestricted field must never be
        blocked just because some OTHER field on the model is readonly
        for this user.

        SECURITY FIX (Phase 8 audit): replaced a bypass-context-alone
        check (a critical, externally-spoofable vulnerability) with a
        self.env.su check - see
        _simplify_enforcement_skipped()'s docstring for the full
        rationale, which applies identically here.
        """
        if self.env.su:
            return
        if self._simplify_is_exempt_model():
            return

        field_policy = self._simplify_get_field_policy()
        if not field_policy:
            return

        for field_name in vals.keys():
            policy = field_policy.get(field_name)
            if not policy or not policy.get('readonly'):
                continue
            field_description = self._simplify_get_field_description(field_name)
            model_description = self._simplify_get_model_description()
            raise AccessError(_(
                'You are not allowed to modify the field %(field)s on '
                '%(model)s.',
                field=field_description, model=model_description,
            ))

    def _simplify_check_required_fields(self, records, touched_field_names=None):
        """Raise ValidationError if any Simplify-required field on
        `records` ends up without a value.

        * touched_field_names is None (create): every field marked
          required by the effective policy is checked against the
          newly-created record's actual resulting state (so ORM defaults
          and onchange-populated values are honoured, not just the raw
          vals that were passed in).
        * touched_field_names is a set (write): only required fields that
          were actually part of THIS write are checked, so writing only
          `email` never fails because some unrelated required `phone` was
          already empty on the record beforehand (Phase 4 section 15) -
          but explicitly clearing a required field in the same write
          still fails, since that field is then in `touched_field_names`
          and its resulting value is checked.

        Conflict handling (Phase 4 section 16): the policy engine itself
        already normalizes required=False whenever invisible=True for the
        same effective field policy entry, so a field the user cannot see
        can never simultaneously block them from saving - see
        simplify.access.policy.get_field_policy().

        SECURITY FIX (Phase 8 audit): replaced a bypass-context-alone
        check (a critical, externally-spoofable vulnerability) with a
        self.env.su check - see
        _simplify_enforcement_skipped()'s docstring for the full
        rationale, which applies identically here.
        """
        if self.env.su:
            return
        if not records:
            return
        if records._simplify_is_exempt_model():
            return

        field_policy = records._simplify_get_field_policy()
        if not field_policy:
            return

        required_field_names = [
            name for name, policy in field_policy.items()
            if policy.get('required') and name in records._fields
        ]
        if not required_field_names:
            return
        if touched_field_names is not None:
            required_field_names = [
                name for name in required_field_names
                if name in touched_field_names
            ]
            if not required_field_names:
                return

        for record in records:
            for field_name in required_field_names:
                if record[field_name]:
                    continue
                field_description = record._simplify_get_field_description(field_name)
                model_description = record._simplify_get_model_description()
                raise ValidationError(_(
                    'The field %(field)s is required on %(model)s for '
                    'your user, but no value was provided.',
                    field=field_description, model=model_description,
                ))

    def _simplify_check_export_field_access(self, fields_to_export):
        """Raise AccessError if:
          * Phase 7 global hide_export is set for the current user
            (blocks export of ANYTHING on this model), OR
          * `fields_to_export` (as passed to export_data()) explicitly
            requests any field marked hide_export by the effective
            Phase 4 field policy.

        Global hide_export always wins over any single unrestricted
        field, per Phase 7 section 9 ("Global export restriction
        wins").

        Only the top-level field on THIS model is checked for the
        Phase 4 part - a dotted/related path such as "partner_id.email"
        targets a field on a DIFFERENT model, which is out of scope for
        this model's own field policy (Phase 4 only configures direct
        fields of the selected model).

        ASSUMPTION FLAGGED FOR MANUAL VERIFICATION: the exact separator
        Odoo 19's export_data() uses for related-field paths in
        `fields_to_export` (historically '.' in some versions, '/' via
        the export wizard's display path in others) was not verified
        against local source. Both are handled defensively below so a
        mismatch only means the export-picker restriction is not applied
        to nested paths - the field name matching for direct, top-level
        fields (the common case) does not depend on this.

        SECURITY FIX (Phase 8 audit): replaced a bypass-context-alone
        check (a critical, externally-spoofable vulnerability) with a
        self.env.su check - see
        _simplify_enforcement_skipped()'s docstring for the full
        rationale, which applies identically here.
        """
        if self.env.su:
            return
        if self._simplify_is_exempt_model():
            return

        global_policy = self._simplify_get_global_policy()
        if global_policy.get('hide_export'):
            model_description = self._simplify_get_model_description()
            raise AccessError(_(
                'You are not allowed to export records of %(model)s.',
                model=model_description,
            ))

        field_policy = self._simplify_get_field_policy()
        if not field_policy:
            return

        forbidden_descriptions = []
        for field_path in fields_to_export or []:
            base_field_name = field_path.split('.')[0].split('/')[0]
            policy = field_policy.get(base_field_name)
            if policy and policy.get('hide_export'):
                forbidden_descriptions.append(
                    self._simplify_get_field_description(base_field_name)
                )

        if forbidden_descriptions:
            model_description = self._simplify_get_model_description()
            raise AccessError(_(
                'You are not allowed to export the following field(s) on '
                '%(model)s: %(fields)s.',
                model=model_description,
                fields=', '.join(sorted(set(forbidden_descriptions))),
            ))

    # ------------------------------------------------------------------
    # Phase 5 - Domain (record-level) checks
    # ------------------------------------------------------------------
    # ARCHITECTURE: this never creates, writes to, or reads extra fields
    # on any native Odoo security model (ir.rule, res.groups, ...).
    # Restrictions are resolved fresh from simplify.access.domain
    # configuration on every call via simplify.access.policy.
    # get_domain_policy() and applied dynamically right here - native
    # ir.rule and ir.model.access remain completely independent and are
    # always evaluated by Odoo itself on top of this.
    def _simplify_enforcement_skipped(self):
        """True if Simplify enforcement must be skipped entirely for the
        current call - shared by Phase 5 (domain) and Phase 6
        (button/tab/view/action/report) checks, per the "do not
        duplicate the policy engine" instruction:

        * self._name is an exempt model (see _simplify_is_exempt_model),
          or
        * the current environment is already sudo()-elevated
          (self.env.su) - Simplify's restrictions are meant to apply to
          the ordinary, non-elevated actions of a targeted human user,
          the same way native ir.rule itself is skipped for
          sudo()-elevated calls. Without this, unrelated internal Odoo
          mechanisms that legitimately use sudo() (mail delivery, cron
          jobs, scheduled/system-run actions, other modules' internal
          operations) could be broken by a restriction that was never
          meant to apply to them.

        SECURITY FIX (Phase 8 audit): this method previously ALSO
        treated the presence of the internal ``simplify_access_bypass``
        context key ALONE (i.e. without also requiring self.env.su) as
        sufficient to skip enforcement. Since Odoo context dictionaries
        are part of the RPC call parameters and are therefore under the
        CALLER's control, this meant ANY external caller could bypass
        every Simplify restriction on ANY model simply by adding
        ``context: {"simplify_access_bypass": true}`` to their own
        request - with no privilege required at all. This was a
        critical vulnerability. Every legitimate internal use of this
        context key in this module is ALWAYS paired with .sudo() (see
        every ``self.env['simplify.access.policy'].sudo().with_context(
        simplify_access_bypass=True)`` call site), so the env.su check
        below already correctly and safely covers every legitimate
        internal case on its own - the standalone context-only branch
        was redundant for legitimate use AND was the actual security
        hole, so it has been removed entirely rather than merely
        tightened, eliminating the dead/dangerous code path outright.
        """
        if self._simplify_is_exempt_model():
            return True
        if self.env.su:
            return True
        return False

    def _simplify_domain_enforcement_skipped(self):
        """Backward-compatible alias for _simplify_enforcement_skipped(),
        kept unchanged so already-verified Phase 5 code (which calls
        this exact method name) is not touched.
        """
        return self._simplify_enforcement_skipped()

    def _simplify_get_domain_policy(self, operation):
        """Resolve the effective Phase 5 combined domain for `operation`
        ('read'/'write'/'unlink'/'create') on self._name, for the
        current user/company, or None if no restriction applies. Same
        bypass-context/sudo() recursion guard as the Phase 2/4 policy
        helpers above.
        """
        policy_helper = self.env['simplify.access.policy'].sudo().with_context(
            **{SIMPLIFY_ACCESS_BYPASS_KEY: True}
        )
        return policy_helper.get_domain_policy(
            self._name, operation, user=self.env.user, company=self.env.company,
        )

    # ASSUMPTION FLAGGED FOR MANUAL VERIFICATION: recordset.
    # filtered_domain(domain) - testing which records of an
    # already-fetched recordset match a domain, purely in memory - has
    # been a stable Odoo ORM recordset method for a number of major
    # versions. It was not verified against local Odoo 19 source. It is
    # used here (rather than a fresh search()) specifically so this
    # check never re-queries or sudo()'s the business table - it only
    # evaluates records the caller already legitimately obtained/created
    # in this same call, which keeps this fully aligned with "do not
    # sudo the business search, do not bypass native ir.rule".
    def _simplify_check_domain_access(self, records, operation):
        """Raise AccessError if ANY record in `records` does not satisfy
        the effective Phase 5 domain policy for `operation`
        ('write'/'unlink'/'create'). Never silently drops the forbidden
        subset - the whole operation is rejected if even one record
        fails, per Phase 5 sections 12-16.
        """
        if self._simplify_domain_enforcement_skipped():
            return
        if not records:
            return

        domain_value = records._simplify_get_domain_policy(operation)
        if not domain_value:
            return

        allowed = records.filtered_domain(domain_value)
        forbidden = records - allowed
        if not forbidden:
            return

        model_description = records._simplify_get_model_description()
        messages = {
            'write': _(
                'You are not allowed to modify one or more of the '
                'selected records of %(model)s.', model=model_description,
            ),
            'unlink': _(
                'You are not allowed to delete one or more of the '
                'selected records of %(model)s.', model=model_description,
            ),
            'create': _(
                'You cannot create this record of %(model)s because it '
                'does not satisfy your access rules.',
                model=model_description,
            ),
        }
        raise AccessError(messages[operation])

    def _simplify_check_domain_read_access(self):
        """Defense-in-depth for direct known-ID access (Phase 5 section
        12/Test F): raise AccessError before any field value is read if
        self does not satisfy the effective read-domain policy. Never
        includes the record's own data in the error message.
        """
        if self._simplify_domain_enforcement_skipped():
            return
        if not self:
            return
        domain_value = self._simplify_get_domain_policy('read')
        if not domain_value:
            return
        allowed = self.filtered_domain(domain_value)
        forbidden = self - allowed
        if not forbidden:
            return
        raise AccessError(_('You are not allowed to access this record.'))

    def _simplify_apply_domain_read_policy(self, domain):
        """Return `domain` ANDed with the effective Phase 5 read-domain
        policy for self._name, or `domain` unchanged if no restriction
        applies. Uses odoo.osv.expression.AND - the standard,
        long-established Odoo domain-combination utility - rather than
        hand-building prefix-notation domains.
        """
        if self._simplify_domain_enforcement_skipped():
            return domain
        domain_value = self._simplify_get_domain_policy('read')
        if not domain_value:
            return domain
        return expression.AND([domain or [], domain_value])

    # ------------------------------------------------------------------
    # ORM overrides
    # ------------------------------------------------------------------
    # ASSUMPTION FLAGGED FOR MANUAL VERIFICATION:
    # This module was built without access to the local Odoo 19 source
    # (no server/filesystem access in this environment). The @api.model_
    # create_multi + create(self, vals_list) signature below matches the
    # ORM pattern used since Odoo 17 (batch create as the only supported
    # form, with the single-dict create(vals) shim removed from public
    # model classes). Please confirm this still matches
    # odoo/models.py::BaseModel.create() in your actual Odoo 19 checkout
    # before relying on this in anything beyond your own testing - if the
    # signature differs, this override will fail loudly at import/runtime
    # (not silently), so any mismatch will surface immediately on module
    # upgrade.
    @api.model_create_multi
    def create(self, vals_list):
        self._simplify_check_model_access('create')
        records = super().create(vals_list)
        # Required-field validation happens AFTER creation, against the
        # records' actual resulting state (see
        # _simplify_check_required_fields docstring) - if it raises, the
        # surrounding Odoo transaction is rolled back normally, so no
        # half-created record is left behind.
        self._simplify_check_required_fields(records, touched_field_names=None)
        # Phase 5: validate newly created records against the effective
        # create-domain policy, AFTER creation, in the SAME transaction -
        # if this raises, Odoo's normal transaction rollback removes the
        # unauthorized record(s) automatically. No manual commit, no new
        # cursor - see _simplify_check_domain_access docstring.
        self._simplify_check_domain_access(records, 'create')
        return records

    def write(self, vals):
        self._simplify_check_model_access('write')
        self._simplify_check_field_write_access(vals)
        # Phase 7: archive/unarchive is represented as a write to the
        # `active` field - checked here, in the SAME existing write()
        # path, rather than as a separate override.
        self._simplify_check_archive_access(vals)
        # Phase 5: verify EVERY record in self satisfies the write-domain
        # policy BEFORE performing the write - a multi-record write is
        # rejected entirely if even one record is forbidden, never
        # partially applied to the allowed subset.
        self._simplify_check_domain_access(self, 'write')
        result = super().write(vals)
        self._simplify_check_required_fields(self, touched_field_names=set(vals.keys()))
        return result

    def unlink(self):
        self._simplify_check_model_access('unlink')
        # Phase 5: verify EVERY record in self satisfies the
        # unlink-domain policy BEFORE deleting - never silently delete
        # an allowed subset while rejecting the rest.
        self._simplify_check_domain_access(self, 'unlink')
        return super().unlink()

    def _simplify_check_archive_access(self, vals):
        """Raise AccessError if `vals` toggles the `active` field and
        the current user is Phase-7-restricted from doing so
        (hide_archive for active=False, hide_unarchive for active=True).

        Only applies to genuinely USER-originated writes - internal/
        system operations (sudo()-elevated, e.g. automated archival by
        another module, or the internal bypass context) are already
        excluded by `_simplify_enforcement_skipped()`-equivalent checks
        below, exactly as required by Phase 7 section 10 ("do not block
        every write containing active blindly if it is an internal
        system operation").
        """
        if 'active' not in vals:
            return
        if self._simplify_enforcement_skipped():
            return
        if self._simplify_is_exempt_model():
            return

        global_policy = self._simplify_get_global_policy()
        target_value = vals.get('active')
        if target_value is False and global_policy.get('hide_archive'):
            model_description = self._simplify_get_model_description()
            raise AccessError(_(
                'You are not allowed to archive records of %(model)s.',
                model=model_description,
            ))
        if target_value is True and global_policy.get('hide_unarchive'):
            model_description = self._simplify_get_model_description()
            raise AccessError(_(
                'You are not allowed to restore (unarchive) records of '
                '%(model)s.', model=model_description,
            ))

    # ASSUMPTION FLAGGED FOR MANUAL VERIFICATION: load(self, fields,
    # data) has been the long-standing bulk-import entry point used by
    # both the web client's Import feature and classic XML/CSV data
    # loading. Not verified against local Odoo 19 source. *args/**kwargs
    # are NOT used here (only two parameters have ever existed for this
    # method historically) - if the signature has changed, this will
    # fail loudly and immediately on the very first import attempt, not
    # silently.
    def load(self, fields, data):
        self._simplify_check_import_access()
        return super().load(fields, data)

    def _simplify_check_import_access(self):
        if self._simplify_enforcement_skipped():
            return
        if self._simplify_is_exempt_model():
            return
        global_policy = self._simplify_get_global_policy()
        if global_policy.get('hide_import'):
            raise AccessError(_(
                'You are not allowed to import records.'
            ))

    # ASSUMPTION FLAGGED FOR MANUAL VERIFICATION: copy(self,
    # default=None) has been an extremely stable signature for
    # BaseModel.copy() across many Odoo versions - one of the more
    # confidently-assumed signatures in this build. Not verified against
    # local Odoo 19 source.
    def copy(self, default=None):
        self._simplify_check_duplicate_access()
        return super().copy(default=default)

    def _simplify_check_duplicate_access(self):
        if self._simplify_enforcement_skipped():
            return
        if self._simplify_is_exempt_model():
            return
        global_policy = self._simplify_get_global_policy()
        if global_policy.get('hide_duplicate'):
            model_description = self._simplify_get_model_description()
            raise AccessError(_(
                'You are not allowed to duplicate records of %(model)s.',
                model=model_description,
            ))

    # ASSUMPTION FLAGGED FOR MANUAL VERIFICATION: `_search` is Odoo's
    # long-standing internal search implementation, called by search(),
    # search_count(), search_read() and most list/kanban/form record
    # loading. Importantly, it is a PRIVATE method (leading underscore),
    # meaning it is never directly reachable via external RPC dispatch -
    # unlike get_views(), which is what caused the Phase 4 bug
    # specifically because it IS an RPC entry point. This significantly
    # lowers (though does not eliminate) the risk of this override: a
    # signature mismatch here would surface as an ordinary Python
    # TypeError the moment any search() call reaches it - immediately
    # and visibly on the very first page load - rather than the
    # confusing, unrelated-looking RPC IndexError seen in Phase 4.
    #
    # The exact keyword parameters after `domain` (offset, limit, order,
    # count, and any others) and Odoo 19's exact return type for this
    # method were NOT verified against local source. To minimize risk,
    # this override touches ONLY the first parameter (`domain` - by far
    # the most stable part of this method's signature across every Odoo
    # version) and forwards everything else completely unchanged via
    # *args/**kwargs, and never inspects or transforms whatever super()
    # returns - so whether it returns a list of ids or a Query object
    # (both have existed across different Odoo versions), this override
    # is agnostic to that and simply passes it through.
    def _search(self, domain, *args, **kwargs):
        domain = self._simplify_apply_domain_read_policy(domain)
        return super()._search(domain, *args, **kwargs)

    # ASSUMPTION FLAGGED FOR MANUAL VERIFICATION: read(self, fields=None,
    # load='_classic_read') has had an extremely stable signature across
    # many Odoo versions. This is added as defense-in-depth specifically
    # for the "user manually opens/RPCs a known forbidden record ID"
    # case (Phase 5 section 12/Test F): it raises BEFORE calling
    # super().read(), so a forbidden record's field values are never
    # fetched or returned at all - this is not redundant with _search()
    # above, since a raw browse() on a known id does not go through
    # _search().
    def read(self, fields=None, load='_classic_read'):
        self._simplify_check_domain_read_access()
        return super().read(fields=fields, load=load)

    # ASSUMPTION FLAGGED FOR MANUAL VERIFICATION: export_data()'s exact
    # Odoo 19 signature was not verified against local source (the
    # `raw_data` parameter present in some past versions may or may not
    # still exist). *args/**kwargs are forwarded untouched to super() so
    # this override works regardless of the exact parameter list, and
    # only inspects `fields_to_export` (the one parameter the Phase 4
    # spec explicitly requires - the list of field paths being
    # requested), which has been a stable first positional argument
    # across versions.
    def export_data(self, fields_to_export, *args, **kwargs):
        self._simplify_check_export_field_access(fields_to_export)
        return super().export_data(fields_to_export, *args, **kwargs)

    # ASSUMPTION FLAGGED FOR MANUAL VERIFICATION: get_views() has been the
    # Odoo 16-19 method that returns the combined {'views': {...}, ...}
    # payload for a set of requested view types, replacing the older
    # per-type fields_view_get(). The exact shape of the returned dict
    # (in particular whether shared field metadata lives at a top-level
    # 'fields' key) was not verified against local Odoo 19 source. To
    # keep the blast radius of a wrong assumption as small as possible -
    # this method is called on EVERY view load for EVERY model in the
    # system - only the postprocessing step below is wrapped in a
    # try/except: if applying the field policy fails for any reason, the
    # native, unmodified result from super() is returned as a safe
    # fallback and a warning is logged, rather than breaking view loading
    # module-wide. The native super() call itself is never wrapped, so a
    # genuine Odoo-side error still surfaces normally.
    #
    # FIX: this override was previously missing @api.model. Native
    # get_views() is a model-level method (called by the web client with
    # no record ids). Without the decorator, this override broke that
    # calling convention for EVERY model in the registry (since _inherit
    # = 'base' applies it everywhere), which surfaced as an unrelated-
    # looking "IndexError: list index out of range" inside
    # odoo/service/model.py's RPC dispatch (ids, args = args[0], args[1:])
    # the first time any model - including ir.module.module during
    # upgrade - had its views loaded. @api.model is now applied, matching
    # the native signature exactly.
    @api.model
    def get_views(self, views, options=None):
        result = super().get_views(views, options=options)
        self._simplify_apply_view_policies_to_get_views_result(result)
        return result

    def _simplify_apply_view_policies_to_get_views_result(self, result):
        """Orchestrator for Phase 4 (field policy), Phase 6
        (button/tab), and Phase 7 (best-effort chatter visibility)
        postprocessing of one get_views() result - deliberately kept as
        ONE method with ONE try/except and ONE XML parse-per-view, per
        the explicit Phase 6 instruction not to add a second, unrelated
        get_views override or a second XML parser.

        NOTE: view-TYPE/specific-view hiding (simplify.access.view) is
        intentionally NOT applied here - see
        _simplify_patch_get_views_result()'s docstring for why removing
        view types from get_views() results caused a real Owl crash.
        That restriction is enforced at the action-advertisement layer
        instead (models/access_action_report_native.py).

        KNOWN LIMITATION (Phase 7 hide_chatter): the attempt to hide the
        <chatter/> arch node below is best-effort and UNVERIFIED against
        local Odoo 19 source - see _simplify_patch_arch_tree()'s
        docstring. The authoritative security boundary for chatter is
        the server-side message_post()/mail.activity.create() blocking
        in models/access_mail.py, not this visual hint.

        UI HARDENING (later audit): also patches the root <list>/<form>
        node's native create/edit/delete attributes when Phase 2
        (restrict_create/write/unlink) or Phase 7 (global_readonly)
        restrict this user - see _simplify_patch_arch_tree()'s docstring
        for the mechanism and its own confidence/verification notes.
        This reuses the SAME existing, already-proven arch-patching
        pipeline; no new get_views override, no new JS, no per-model
        special-casing - it is a generic Odoo view-arch mechanism that
        works identically for every model.

        SECURITY FIX (Phase 8 audit): replaced a bypass-context-alone
        check (a critical, externally-spoofable vulnerability) with a
        self.env.su check - see
        _simplify_enforcement_skipped()'s docstring for the full
        rationale, which applies identically here. The Phase 6
        discovery wizard, the one legitimate caller that previously
        relied on the bare context key here, was updated to also use
        .sudo() (see models/access_view_element_picker.py) so it
        continues to correctly see the unfiltered architecture.
        """
        if self.env.su:
            return
        if self._simplify_is_exempt_model():
            return
        try:
            field_policy = self._simplify_get_field_policy()
            button_policy = self._simplify_get_hidden_buttons_policy()
            tab_policy = self._simplify_get_hidden_tabs_policy()
            global_policy = self._simplify_get_global_policy()
            model_policy = self._simplify_get_model_policy()
            if not (field_policy or button_policy or tab_policy
                    or global_policy.get('hide_chatter')
                    or global_policy.get('global_readonly')
                    or any(model_policy.values())):
                return
            self._simplify_patch_get_views_result(
                result, field_policy, button_policy, tab_policy, global_policy,
                model_policy,
            )
        except Exception:
            _logger.warning(
                'simplify_access_management: failed to apply Simplify '
                'view policies to get_views() result for model %s; '
                'returning the native view unmodified as a safe '
                'fallback.', self._name, exc_info=True,
            )

    def _simplify_get_hidden_buttons_policy(self):
        policy_helper = self.env['simplify.access.policy'].sudo().with_context(
            **{SIMPLIFY_ACCESS_BYPASS_KEY: True}
        )
        return policy_helper.get_hidden_buttons_policy(
            self._name, user=self.env.user, company=self.env.company,
        )

    def _simplify_get_hidden_tabs_policy(self):
        policy_helper = self.env['simplify.access.policy'].sudo().with_context(
            **{SIMPLIFY_ACCESS_BYPASS_KEY: True}
        )
        return policy_helper.get_hidden_tabs_policy(
            self._name, user=self.env.user, company=self.env.company,
        )

    def _simplify_get_hidden_view_policy(self):
        policy_helper = self.env['simplify.access.policy'].sudo().with_context(
            **{SIMPLIFY_ACCESS_BYPASS_KEY: True}
        )
        return policy_helper.get_hidden_view_policy(
            self._name, user=self.env.user, company=self.env.company,
        )

    def _simplify_patch_get_views_result(self, result, field_policy, button_policy,
                                          tab_policy, global_policy=None,
                                          model_policy=None):
        """Patch field/button/tab modifiers, best-effort chatter
        visibility, and native create/edit/delete availability into the
        architecture of each view type Odoo actually returns.

        IMPORTANT ARCHITECTURE NOTE (fix for a real Owl crash): this
        method used to ALSO remove entire view types from `result` when
        restricted by simplify.access.view (view-type/specific-view
        hiding). That was wrong: get_views() must always be able to
        return a valid architecture for any view type/id it is actually
        asked for - removing it here caused the web client (which had
        already decided to render that view type's icon/tab based on
        the ACTION's own view list, a separate code path this method
        never touched) to request an architecture that silently wasn't
        there, producing "TypeError: Cannot read properties of undefined
        (reading 'arch')".

        View-TYPE/specific-view hiding is UI AVAILABILITY control, not
        model security - underlying data access is already governed by
        native ACL, native record rules, Phase 2 (model access) and
        Phase 5 (domain access), none of which are affected by this
        method either way. The correct, and now sole, enforcement point
        for view-type/view-id hiding is
        ir.actions.act_window._get_action_dict() (see
        models/access_action_report_native.py): it prevents the
        restricted view type from ever being ADVERTISED as available in
        the first place, so the client never requests it through this
        method at all in ordinary navigation.
        """
        views_data = result.get('views') if isinstance(result, dict) else None
        if not views_data:
            return

        hide_chatter = bool(global_policy and global_policy.get('hide_chatter'))
        global_policy = global_policy or {}
        model_policy = model_policy or {}
        global_readonly = bool(global_policy.get('global_readonly'))
        restrict_create = global_readonly or bool(model_policy.get('restrict_create'))
        restrict_write = global_readonly or bool(model_policy.get('restrict_write'))
        restrict_unlink = global_readonly or bool(model_policy.get('restrict_unlink'))

        # ---- Phase 4 + Phase 6 + Phase 7: patch views' architecture ----
        for view_type, view_data in views_data.items():
            if view_type not in ('form', 'list', 'kanban', 'search'):
                continue
            if not isinstance(view_data, dict):
                continue
            arch = view_data.get('arch')
            if not arch:
                continue
            tree = etree.fromstring(
                arch.encode('utf-8') if isinstance(arch, str) else arch
            )
            resolved_view_id = view_data.get('id')
            changed = self._simplify_patch_arch_tree(
                tree, field_policy, button_policy, tab_policy, resolved_view_id,
                hide_chatter=hide_chatter,
                restrict_create=restrict_create,
                restrict_write=restrict_write,
                restrict_unlink=restrict_unlink,
            )
            if changed:
                view_data['arch'] = etree.tostring(tree, encoding='unicode')

        # Best-effort only, deliberately isolated from the arch patching
        # above via the outer try/except in the caller: strip explicitly
        # invisible fields from the shared field-metadata dict, if one is
        # present at this key, so dynamically generated selectors (e.g.
        # "Add Custom Filter", Group By) do not offer them either. If this
        # key does not exist in this Odoo 19 version's get_views() return
        # shape, this is simply a no-op.
        fields_meta = result.get('fields') if isinstance(result, dict) else None
        if isinstance(fields_meta, dict):
            for field_name, policy in field_policy.items():
                if policy.get('invisible'):
                    fields_meta.pop(field_name, None)

    def _simplify_patch_arch_tree(self, tree, field_policy, button_policy=None,
                                   tab_policy=None, current_view_id=None,
                                   hide_chatter=False, restrict_create=False,
                                   restrict_write=False, restrict_unlink=False):
        """Apply Phase 4 field modifiers, Phase 6 button/tab hiding, a
        best-effort Phase 7 chatter-visibility hint, and native
        create/edit/delete availability directly onto an already-
        generated view architecture tree, in place, in a SINGLE pass
        (one parse, one set of node-type iterations, one caller-side
        re-serialization) - never a second parser, per the Phase 6
        instruction to reuse this existing engine. Never deletes nodes
        and never writes back to any stored ir.ui.view record - `tree`
        is a transient, in-memory copy built fresh for this one request
        (see get_views() above), discarded after this request completes.

        button_policy/tab_policy entries with view_id=False apply to ANY
        view of this model; entries with a specific view_id only apply
        when current_view_id matches it.

        ASSUMPTION FLAGGED AND KNOWN LIMITATION (hide_chatter): a
        <chatter/> arch tag is the Odoo convention I am aware of for
        recent versions' mail-thread widget declaration in form views,
        but this was NOT verified against local Odoo 19 source, and no
        JavaScript/Owl-component changes are made anywhere in this
        module (I have no way to verify Odoo 19's frontend
        service/component architecture without source or runtime
        access, and a wrong guess there risks a much larger blast
        radius - a broken web client - than a Python exception would).
        If this tag name/attribute is wrong for your version, the
        chatter panel will simply remain visible for the current
        request (silently, no error, since this is wrapped in the same
        outer try/except as everything else in this pipeline) - the
        authoritative, always-correct security boundary is the
        server-side message_post()/mail.activity.create() blocking in
        models/access_mail.py, which does not depend on this at all.

        ASSUMPTION FLAGGED (restrict_create/write/unlink - UI hardening
        audit): the root <list>/<form>/<kanban> arch node's own
        create/edit/delete boolean attributes (e.g. <list create="1"
        edit="1" delete="1">) are the long-standing, generic Odoo
        mechanism that feeds the client's `activeActions` computation -
        this drives the New button, inline/quick edit, and Delete action
        generically for EVERY model, with no per-model special-casing
        needed. This is a well-established, stable Odoo view convention
        (not a guessed internal component path), so confidence here is
        higher than the hide_chatter case above. Only ever sets these
        attributes to "false" when Simplify restricts - Simplify never
        sets them to "true", so a model where native Odoo already
        disabled create/edit/delete (e.g. a genuinely readonly report
        view) is never granted anything it didn't already have. If this
        specific attribute convention is wrong for your version, the
        corresponding button/control simply remains visible for the
        current request (same safe, silent degradation as hide_chatter)
        - backend create()/write()/unlink() enforcement in this same
        file is completely independent of this and remains authoritative
        regardless.

        Returns True if anything was changed, so the caller only needs
        to re-serialize the tree when necessary.
        """
        button_policy = button_policy or []
        tab_policy = tab_policy or []
        changed = False

        if restrict_create or restrict_write or restrict_unlink:
            root = tree if tree.tag in ('list', 'form', 'kanban') else None
            if root is not None:
                if restrict_create:
                    root.set('create', 'false')
                    if root.tag == 'kanban':
                        # Kanban's inline "quick add" card is a separate
                        # create entry point from the generic New button.
                        root.set('quick_create', 'false')
                if restrict_write:
                    root.set('edit', 'false')
                if restrict_unlink:
                    root.set('delete', 'false')
                changed = True

        if hide_chatter:
            for node in tree.iter('chatter'):
                node.set('invisible', '1')
                changed = True

        for node in tree.iter('field'):
            field_name = node.get('name')
            if not field_name:
                continue
            policy = field_policy.get(field_name)
            if not policy:
                continue

            if policy.get('invisible'):
                # Overwrites any existing conditional invisible modifier:
                # our restriction must always win (most-restrictive-wins),
                # and the field remains present in the architecture (not
                # deleted), so anything that structurally depends on the
                # node continuing to exist keeps working.
                node.set('invisible', '1')
                changed = True

            if policy.get('readonly'):
                node.set('readonly', '1')
                changed = True

            # Conflict safety net (Phase 4 section 16): the policy engine
            # already suppresses required when invisible is True for the
            # same effective entry, but this check is repeated here too
            # so the view-arch layer never marks a field required if it
            # is also being rendered invisible, regardless of how the
            # policy dict was produced.
            if policy.get('required') and not policy.get('invisible'):
                node.set('required', '1')
                changed = True

            if policy.get('remove_external_link'):
                self._simplify_disable_external_link_widget(node)
                changed = True

        if button_policy:
            applicable_buttons = {
                (entry['name'], entry['type']) for entry in button_policy
                if not entry.get('view_id') or entry.get('view_id') == current_view_id
            }
            if applicable_buttons:
                for node in tree.iter('button'):
                    key = (node.get('name'), node.get('type'))
                    if key in applicable_buttons:
                        # Prefer a safe modifier over removing the node:
                        # setting invisible="1" cannot corrupt surrounding
                        # XML/modifiers/domains, unlike deleting a node
                        # that other expressions might structurally rely
                        # on continuing to exist.
                        node.set('invisible', '1')
                        changed = True

        if tab_policy:
            applicable_pages = {
                entry['page_name'] for entry in tab_policy
                if not entry.get('view_id') or entry.get('view_id') == current_view_id
            }
            if applicable_pages:
                for node in tree.iter('page'):
                    if node.get('name') in applicable_pages:
                        node.set('invisible', '1')
                        changed = True

        return changed

    def _simplify_disable_external_link_widget(self, node):
        """Merge {'no_open': True} into the field node's existing
        `options` attribute (Odoo relational-widget convention for
        disabling the external/open-record link), preserving any other
        options already configured on that field in the native view.
        """
        raw_options = node.get('options')
        options = {}
        if raw_options:
            try:
                parsed = ast.literal_eval(raw_options)
                if isinstance(parsed, dict):
                    options = parsed
            except (ValueError, SyntaxError):
                options = {}
        options['no_open'] = True
        node.set('options', repr(options))
