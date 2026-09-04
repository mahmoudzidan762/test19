# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api, models
from odoo.osv import expression
from odoo.tools import ormcache

# Internal, namespaced context key used to signal to the access engine that
# the current call is part of the engine's OWN internal resolution logic and
# must therefore bypass itself. This exists specifically to prevent
# recursive access checks once real enforcement is implemented in later
# phases (e.g. the policy resolver reading simplify.access.rule records
# must not, in turn, be blocked by restrictions derived from those same
# records).
#
# Deliberately namespaced (not a generic name like "bypass_security") to
# avoid clashing with context keys used elsewhere in Odoo or other modules.
SIMPLIFY_ACCESS_BYPASS_KEY = 'simplify_access_bypass'

# XML ID of the group whose members are always exempt from restrictions
# produced by this module (but NOT from native Odoo security, which always
# remains authoritative).
ACCESS_MANAGER_GROUP_XML_ID = (
    'simplify_access_management.group_access_management_manager'
)


class SimplifyAccessPolicy(models.AbstractModel):
    """Central policy helper for the Simplify Access Management engine.

    Phase 1 note
    ------------
    This is the foundation only. The methods below identify *who* is
    exempt from the engine and *which* configuration rules currently apply
    to a given user/company - they do not compute or enforce any concrete
    restriction (readonly, hidden menu, domain, ...). That logic belongs to
    later phases and will be built on top of ``_get_applicable_rules()``.

    Implemented as an AbstractModel (no table) since this is a stateless
    helper, called as ``self.env['simplify.access.policy']._method(...)``.
    """
    _name = 'simplify.access.policy'
    _description = 'Simplify Access Management - Policy Helper'

    # ------------------------------------------------------------------
    # Bypass / exemption resolution
    # ------------------------------------------------------------------
    # NOTE (Phase 8 audit): a method called _is_bypass_context() used to
    # live here, returning whether the current environment's context
    # carried the internal simplify_access_bypass key IN ISOLATION. It
    # had no callers left after an earlier fix (removed from
    # _is_bypass_user(), see below), so it was pure dead code - but its
    # shape was EXACTLY the pattern that turned out to be a critical,
    # externally-spoofable vulnerability everywhere else it was used
    # this way (see models/access_enforcement.py's
    # _simplify_enforcement_skipped() docstring for the full incident).
    # It has been removed entirely, rather than merely left unused, to
    # eliminate any risk of it being reintroduced as a caller by mistake
    # in the future. The correct, un-spoofable signal for "this is an
    # internal/system operation" is self.env.su alone - checked directly
    # wherever needed, with no separate context-based helper at all.

    @api.model
    def _is_access_manager(self, user=None):
        """True if `user` (defaults to the current user) belongs to the
        Access Management Manager group.

        Access Management Managers are exempt from restrictions produced
        by this engine by default, to prevent an administrator from
        accidentally locking themselves - or every manager - out of the
        configuration screens.
        """
        user = user or self.env.user
        if user.id == SUPERUSER_ID:
            return True
        return user.has_group(ACCESS_MANAGER_GROUP_XML_ID)

    @api.model
    def _is_bypass_user(self, user=None):
        """True if `user` (defaults to the current user) must be exempt
        from every restriction produced by this engine.

        This combines exactly two things:
          * SUPERUSER - always bypasses, per Odoo convention.
          * Access Management Manager membership - admin-lockout safety.

        Native Odoo security (ir.model.access, ir.rule, field groups, ...)
        is NEVER affected by this method; it only concerns restrictions
        that this module itself adds.

        BUG FIX (earlier round): this method previously also checked
        the CALLING object's own context for the internal
        ``simplify_access_bypass`` key. In practice, every real caller
        (get_model_policy, get_field_policy, get_hidden_menu_ids,
        get_domain_policy, _get_applicable_rules - see their call sites)
        invokes this method on a ``policy_helper`` object that was
        itself constructed via
        ``self.env['simplify.access.policy'].sudo().with_context(
        simplify_access_bypass=True)`` purely so IT can safely read
        simplify.access.* configuration records without recursively
        re-triggering enforcement on THOSE reads. Because that context
        flag lives on ``policy_helper`` itself (not on the actual TARGET
        user/record being evaluated), checking it here caused
        ``_is_bypass_user()`` to ALWAYS return True for EVERY user,
        including entirely ordinary, non-manager users - silently
        disabling Phase 2/3/4/5 enforcement for everyone, every time,
        confirmed by a real reproduction (a plain user's write to a
        record outside their configured Write Domain was incorrectly
        allowed).

        The fix: this method now ONLY evaluates the `user` argument
        actually passed in (always the real acting user - see every
        caller in models/access_enforcement.py and models/ir_ui_menu.py,
        which all pass ``user=self.env.user`` from the ORIGINAL business
        record, before any sudo()/bypass-context wrapping happens).

        SECURITY FIX (Phase 8 audit, later round): the paragraph above
        originally claimed the SEPARATE recursion-guard mechanism -
        callers checking the bypass context directly on the record
        being read/written, for internal simplify.access.* reads - "was
        never broken and needed no change". That claim was WRONG: that
        exact pattern turned out to be a critical, externally-spoofable
        vulnerability, since Odoo context dictionaries are part of the
        RPC call parameters and are under the CALLER's control - any
        external caller could set ``context: {"simplify_access_bypass":
        true}`` on their OWN request and bypass Simplify enforcement
        entirely, without any privilege at all. Every such check across
        the module (models/access_enforcement.py,
        models/access_mail.py, models/access_module.py,
        models/ir_ui_menu.py) has since been replaced with a plain
        ``self.env.su`` check, which correctly and safely covers every
        legitimate internal case (every internal policy read in this
        module already pairs ``.sudo()`` with this context key) while
        being un-spoofable by an external caller. The now-dead,
        vulnerability-shaped helper this docstring used to reference has
        been removed entirely.
        """
        user = user or self.env.user
        if user.id == SUPERUSER_ID:
            return True
        if self._is_access_manager(user=user):
            return True
        return False

    # ------------------------------------------------------------------
    # Rule resolution
    # ------------------------------------------------------------------
    @api.model
    def _get_applicable_rules(self, user=None, company=None):
        """Return the recordset of ``simplify.access.rule`` that currently
        apply to `user` (defaults to the current user) in `company`
        (defaults to the current active company).

        A rule applies when:
          * active is True, AND
          * `user` is present in the rule's user_ids, AND
          * either apply_all_companies is True, OR `company` is present in
            the rule's company_ids.

        Bypass users (see ``_is_bypass_user``) always resolve to an empty
        recordset - i.e. no restriction can ever apply to them.

        Phase 1 note: this method is exposed as the foundation for later
        phases. Nothing in this module currently reads its result to
        change behaviour - it is not yet wired into any enforcement path.
        """
        user = user or self.env.user
        company = company or self.env.company

        if self._is_bypass_user(user=user):
            return self.env['simplify.access.rule']

        # Use sudo() + the internal bypass context so that resolving the
        # applicable rules can never be blocked by a restriction that is
        # itself derived from those rules (recursion guard). The resulting
        # recordset is only used internally for policy computation; it
        # must never be returned to business logic as-is once enforcement
        # exists.
        rule_model = self.env['simplify.access.rule'].sudo().with_context(
            **{SIMPLIFY_ACCESS_BYPASS_KEY: True}
        )
        candidate_rules = rule_model.search([
            ('active', '=', True),
            ('user_ids', 'in', user.id),
        ])

        applicable_rules = candidate_rules.filtered(
            lambda rule: rule.apply_all_companies or company in rule.company_ids
        )
        return applicable_rules

    # ------------------------------------------------------------------
    # Phase 2 - Effective model policy
    # ------------------------------------------------------------------
    @api.model
    def get_model_policy(self, model_name, user=None, company=None):
        """Return the effective model-level restrictions for `model_name`
        that apply to `user` (defaults to current user) in `company`
        (defaults to current company).

        Normalized result::

            {
                'readonly': bool,
                'restrict_create': bool,
                'restrict_write': bool,
                'restrict_unlink': bool,
            }

        Combination rule (Phase 2): TRUE restriction wins. If any
        applicable simplify.access.model line for this model sets a flag,
        the effective policy has that flag set to True - regardless of
        what other applicable lines say. ``readonly`` additionally implies
        all three restrict_* flags are True for that model line.

        Bypass users (SUPERUSER, internal bypass context, Access
        Management Managers) always get an all-False policy, i.e. no
        restriction.

        PERFORMANCE FIX (Phase 8 audit): this method was the only
        model-scoped policy method NOT backed by ormcache, unlike
        get_field_policy, get_hidden_buttons_policy,
        get_hidden_tabs_policy, get_hidden_view_policy and
        get_domain_policy, which all share this exact pattern. Since a
        single write() call resolves this policy at least once (see
        access_enforcement.py's _simplify_check_model_access), leaving
        it uncached meant a real, avoidable database search on every
        single create/write/unlink for every model, even when nothing
        had changed since the last identical lookup. Now cached per
        (model_name, user_id, company_id), invalidated the same way as
        every other cached policy via clear_caches().
        """
        user = user or self.env.user
        company = company or self.env.company

        effective_policy = {
            'readonly': False,
            'restrict_create': False,
            'restrict_write': False,
            'restrict_unlink': False,
        }

        if self._is_bypass_user(user=user):
            return effective_policy

        flags = self._get_model_policy_cached(model_name, user.id, company.id)
        for field, value in zip(
            ('readonly', 'restrict_create', 'restrict_write', 'restrict_unlink'),
            flags,
        ):
            effective_policy[field] = bool(value)
        return effective_policy

    @ormcache('model_name', 'user_id', 'company_id')
    def _get_model_policy_cached(self, model_name, user_id, company_id):
        user = self.env['res.users'].sudo().browse(user_id)
        company = self.env['res.company'].sudo().browse(company_id)

        applicable_rules = self._get_applicable_rules(user=user, company=company)
        if not applicable_rules:
            return (False, False, False, False)

        # Read model lines with sudo() + the internal bypass context: this
        # is internal policy-resolution machinery reading the engine's own
        # configuration data, not a business operation on behalf of the
        # user, so it must not be subject to the restrictions it is in the
        # process of computing (recursion guard - see module docstring).
        model_lines = self.env['simplify.access.model'].sudo().with_context(
            **{SIMPLIFY_ACCESS_BYPASS_KEY: True}
        ).search([
            ('access_rule_id', 'in', applicable_rules.ids),
            ('model_name', '=', model_name),
        ])

        readonly = restrict_create = restrict_write = restrict_unlink = False
        for line in model_lines:
            if line.readonly:
                readonly = restrict_create = restrict_write = restrict_unlink = True
                continue
            if line.restrict_create:
                restrict_create = True
            if line.restrict_write:
                restrict_write = True
            if line.restrict_unlink:
                restrict_unlink = True

        return (readonly, restrict_create, restrict_write, restrict_unlink)

    # ------------------------------------------------------------------
    # Phase 4 - Effective field policy
    # ------------------------------------------------------------------
    @api.model
    def get_field_policy(self, model_name, user=None, company=None):
        """Return the effective field-level restrictions for every field
        of `model_name` that has at least one applicable
        simplify.access.field line, for `user` (defaults to current user)
        in `company` (defaults to current company).

        Normalized result::

            {
                'email': {
                    'invisible': bool,
                    'readonly': bool,
                    'required': bool,
                    'remove_external_link': bool,
                    'hide_export': bool,
                },
                ...
            }

        Fields with no applicable configuration are simply absent from
        the returned dict (not present with all-False values), so callers
        can cheaply test ``field_name in policy``.

        Combination rule (Phase 4 section 6): TRUE restriction wins - if
        ANY applicable rule's line sets a flag for a given field, the
        effective entry has that flag True, regardless of what other
        applicable lines say for the same field.

        Conflict normalization (Phase 4 section 16): a single
        simplify.access.field line can never have both invisible and
        required True (enforced at the model level via a constraint on
        simplify.access.field itself). However two DIFFERENT applicable
        rules could still combine to produce that conflict (Rule A:
        invisible, Rule B: required, same field) - since invisible must
        always win to keep the form completable, this method forces
        required back to False whenever the combined/effective invisible
        is True, after combining all applicable lines.

        Bypass users (SUPERUSER, internal bypass context, Access
        Management Managers) always get an empty dict, i.e. no
        restriction.

        PERFORMANCE FIX (Phase 8 audit): now cached per (model_name,
        user_id, company_id), matching every other model-scoped policy
        method (get_hidden_buttons_policy, get_hidden_tabs_policy,
        get_hidden_view_policy, get_domain_policy). Previously uncached,
        this method was observed being resolved TWICE within a single
        write() call (once for the readonly check, once again for the
        required-field check afterward) - an avoidable, repeated
        database search for the exact same result. Invalidated the same
        way as every other cached policy via clear_caches().
        """
        user = user or self.env.user
        company = company or self.env.company

        if self._is_bypass_user(user=user):
            return {}

        cached = self._get_field_policy_cached(model_name, user.id, company.id)
        return {
            field_name: dict(entry)
            for field_name, entry in cached
        }

    @ormcache('model_name', 'user_id', 'company_id')
    def _get_field_policy_cached(self, model_name, user_id, company_id):
        user = self.env['res.users'].sudo().browse(user_id)
        company = self.env['res.company'].sudo().browse(company_id)

        applicable_rules = self._get_applicable_rules(user=user, company=company)
        if not applicable_rules:
            return ()

        # Read field lines with sudo() + the internal bypass context: see
        # the recursion-guard rationale in _get_applicable_rules() and
        # get_model_policy() above.
        field_lines = self.env['simplify.access.field'].sudo().with_context(
            **{SIMPLIFY_ACCESS_BYPASS_KEY: True}
        ).search([
            ('access_rule_id', 'in', applicable_rules.ids),
            ('model_name', '=', model_name),
        ])

        effective_policy = {}
        for line in field_lines:
            entry = effective_policy.setdefault(line.field_name, {
                'invisible': False,
                'readonly': False,
                'required': False,
                'remove_external_link': False,
                'hide_export': False,
            })
            if line.invisible:
                entry['invisible'] = True
            if line.readonly:
                entry['readonly'] = True
            if line.required:
                entry['required'] = True
            if line.remove_external_link:
                entry['remove_external_link'] = True
            if line.hide_export:
                entry['hide_export'] = True

        # Cross-rule conflict normalization - see docstring above.
        for entry in effective_policy.values():
            if entry['invisible']:
                entry['required'] = False

        # Return as a tuple of (key, tuple-of-items) pairs - hashable/
        # immutable, safe to cache; reconstructed into plain dicts by
        # the public get_field_policy() wrapper above.
        return tuple(
            (field_name, tuple(entry.items()))
            for field_name, entry in effective_policy.items()
        )

    # ASSUMPTION FLAGGED FOR MANUAL VERIFICATION: this module was built
    # without access to the local Odoo 19 source. `odoo.tools.ormcache`
    # and the per-model `clear_caches()` classmethod have been stable
    # Odoo APIs for many major versions and are used throughout Odoo core
    # for exactly this kind of "expensive to compute, invalidate on
    # write" caching. Please confirm both still exist as used here in
    # your Odoo 19 checkout - a mismatch will raise an ImportError or
    # AttributeError immediately on module load/upgrade (fails loudly,
    # not silently).
    @api.model
    def get_hidden_menu_ids(self, user=None, company=None):
        """Return the set of ir.ui.menu ids that must be hidden from
        navigation for `user` (defaults to current user) in `company`
        (defaults to current company).

        This is the UNION of every menu explicitly configured on every
        applicable simplify.access.rule (via simplify.access.menu lines),
        expanded to include each hidden menu's full descendant subtree -
        hiding a parent hides its children, but hiding a child never
        affects its parent or siblings.

        Bypass users (SUPERUSER, internal bypass context, Access
        Management Managers) always resolve to an empty set.

        The expensive part (resolving rules/menu lines and expanding the
        menu subtree) is cached per (user, company) via ormcache and
        invalidated by simplify.access.rule/simplify.access.menu
        create/write/unlink - see those models. This method itself stays
        uncached so the bypass check always reflects the current context.
        """
        user = user or self.env.user
        company = company or self.env.company

        if self._is_bypass_user(user=user):
            return set()

        return set(self._get_hidden_menu_ids_cached(user.id, company.id))

    @ormcache('user_id', 'company_id')
    def _get_hidden_menu_ids_cached(self, user_id, company_id):
        """Cached computation backing get_hidden_menu_ids(). Do not call
        directly from outside this class - always go through
        get_hidden_menu_ids() so the bypass check is applied first.
        """
        user = self.env['res.users'].sudo().browse(user_id)
        company = self.env['res.company'].sudo().browse(company_id)

        applicable_rules = self._get_applicable_rules(user=user, company=company)
        if not applicable_rules:
            return frozenset()

        bypass_context = {SIMPLIFY_ACCESS_BYPASS_KEY: True}
        menu_lines = self.env['simplify.access.menu'].sudo().with_context(
            **bypass_context
        ).search([
            ('access_rule_id', 'in', applicable_rules.ids),
        ])

        explicit_menu_ids = menu_lines.mapped('menu_id').ids
        if not explicit_menu_ids:
            return frozenset()

        # Single query: expand every explicitly-hidden menu to include its
        # full descendant subtree, so a hidden parent also hides its
        # children (child_of does this natively and avoids N+1 lookups).
        expanded_menus = self.env['ir.ui.menu'].sudo().with_context(
            **bypass_context
        ).search([('id', 'child_of', explicit_menu_ids)])

        return frozenset(expanded_menus.ids)

    # ------------------------------------------------------------------
    # Phase 5 - Effective domain (record-level) policy
    # ------------------------------------------------------------------
    # ARCHITECTURE: unlike an earlier revision of this phase, this method
    # does NOT generate or depend on native ir.rule records. It purely
    # resolves the combined domain from simplify.access.domain
    # configuration; models/access_enforcement.py applies the result
    # dynamically (ANDed onto the incoming search domain, or validated
    # against records on write/unlink/create) without ever creating,
    # writing to, or reading extra fields on any native Odoo security
    # model. Native ir.rule and ir.model.access remain fully independent
    # and are always evaluated by Odoo itself, on top of this.
    @api.model
    def get_domain_policy(self, model_name, operation, user=None, company=None):
        """Return the effective combined domain (a plain Odoo domain
        list) that restricts `operation` ('read', 'write', 'unlink' or
        'create') on `model_name` for `user` (defaults to current user)
        in `company` (defaults to current company), or None if no
        restriction applies for that operation.

        Combination rule (Phase 5 section 8): every applicable
        simplify.access.domain line with apply_<operation>=True is
        combined using AND (odoo.osv.expression.AND), never OR - most
        restrictive wins, exactly like every other policy in this
        module.

        Bypass users (SUPERUSER, internal bypass context, Access
        Management Managers) always get None, i.e. no restriction.
        """
        user = user or self.env.user
        company = company or self.env.company

        if operation not in ('read', 'write', 'unlink', 'create'):
            raise ValueError(
                "get_domain_policy(): operation must be one of "
                "'read'/'write'/'unlink'/'create', got %r" % (operation,)
            )

        if self._is_bypass_user(user=user):
            return None

        cached_domain = self._get_domain_policy_cached(
            model_name, operation, user.id, company.id,
        )
        return list(cached_domain) if cached_domain is not None else None

    @ormcache('model_name', 'operation', 'user_id', 'company_id')
    def _get_domain_policy_cached(self, model_name, operation, user_id, company_id):
        """Cached computation backing get_domain_policy(). Do not call
        directly from outside this class - always go through
        get_domain_policy() so the bypass check is applied first.

        Returns a tuple (immutable, safe to cache) or None.
        """
        user = self.env['res.users'].sudo().browse(user_id)
        company = self.env['res.company'].sudo().browse(company_id)

        applicable_rules = self._get_applicable_rules(user=user, company=company)
        if not applicable_rules:
            return None

        bypass_context = {SIMPLIFY_ACCESS_BYPASS_KEY: True}
        domain_lines = self.env['simplify.access.domain'].sudo().with_context(
            **bypass_context
        ).search([
            ('access_rule_id', 'in', applicable_rules.ids),
            ('model_name', '=', model_name),
            ('active', '=', True),
            ('apply_%s' % operation, '=', True),
        ])
        if not domain_lines:
            return None

        domains = []
        for line in domain_lines:
            domain_value = line._simplify_safe_eval_domain()
            if isinstance(domain_value, (list, tuple)) and domain_value:
                domains.append(list(domain_value))

        if not domains:
            return None

        combined = expression.AND(domains) if len(domains) > 1 else domains[0]
        return tuple(combined)

    # ------------------------------------------------------------------
    # Phase 6 - Buttons, Tabs, Views, Actions, Reports
    # ------------------------------------------------------------------
    # All UNION-combined (additive) across applicable rules, per Phase 6
    # section 23 - unlike the TRUE-wins boolean combination of Phase 2/4
    # or the AND combination of Phase 5 domains, "hidden item" sets from
    # different rules simply union together.
    @api.model
    def get_hidden_buttons_policy(self, model_name, user=None, company=None):
        """Return a list of {'name', 'type', 'view_id'} dicts describing
        every button hidden for `user` in `company` on `model_name`.
        `view_id` is False/None for a model-wide rule (any view), or a
        specific ir.ui.view id.
        """
        user = user or self.env.user
        company = company or self.env.company
        if self._is_bypass_user(user=user):
            return []
        cached = self._get_hidden_buttons_policy_cached(model_name, user.id, company.id)
        return [dict(entry) for entry in cached]

    @ormcache('model_name', 'user_id', 'company_id')
    def _get_hidden_buttons_policy_cached(self, model_name, user_id, company_id):
        user = self.env['res.users'].sudo().browse(user_id)
        company = self.env['res.company'].sudo().browse(company_id)
        applicable_rules = self._get_applicable_rules(user=user, company=company)
        if not applicable_rules:
            return ()
        lines = self.env['simplify.access.button'].sudo().with_context(
            **{SIMPLIFY_ACCESS_BYPASS_KEY: True}
        ).search([
            ('access_rule_id', 'in', applicable_rules.ids),
            ('model_name', '=', model_name),
            ('active', '=', True),
        ])
        return tuple(
            {'name': line.button_name, 'type': line.button_type,
             'view_id': line.view_id.id or False}
            for line in lines
        )

    @api.model
    def get_hidden_tabs_policy(self, model_name, user=None, company=None):
        """Return a list of {'page_name', 'view_id'} dicts describing
        every notebook tab hidden for `user` in `company` on
        `model_name`. `view_id` is False/None for a model-wide rule.
        """
        user = user or self.env.user
        company = company or self.env.company
        if self._is_bypass_user(user=user):
            return []
        cached = self._get_hidden_tabs_policy_cached(model_name, user.id, company.id)
        return [dict(entry) for entry in cached]

    @ormcache('model_name', 'user_id', 'company_id')
    def _get_hidden_tabs_policy_cached(self, model_name, user_id, company_id):
        user = self.env['res.users'].sudo().browse(user_id)
        company = self.env['res.company'].sudo().browse(company_id)
        applicable_rules = self._get_applicable_rules(user=user, company=company)
        if not applicable_rules:
            return ()
        lines = self.env['simplify.access.tab'].sudo().with_context(
            **{SIMPLIFY_ACCESS_BYPASS_KEY: True}
        ).search([
            ('access_rule_id', 'in', applicable_rules.ids),
            ('model_name', '=', model_name),
            ('active', '=', True),
        ])
        return tuple(
            {'page_name': line.page_name, 'view_id': line.view_id.id or False}
            for line in lines
        )

    @api.model
    def get_hidden_view_policy(self, model_name, user=None, company=None):
        """Return {'view_ids': set(...), 'view_types': set(...)} - the
        specific ir.ui.view ids and/or whole view types restricted for
        `user` in `company` on `model_name`.
        """
        user = user or self.env.user
        company = company or self.env.company
        if self._is_bypass_user(user=user):
            return {'view_ids': set(), 'view_types': set()}
        view_ids, view_types = self._get_hidden_view_policy_cached(
            model_name, user.id, company.id,
        )
        return {'view_ids': set(view_ids), 'view_types': set(view_types)}

    @ormcache('model_name', 'user_id', 'company_id')
    def _get_hidden_view_policy_cached(self, model_name, user_id, company_id):
        user = self.env['res.users'].sudo().browse(user_id)
        company = self.env['res.company'].sudo().browse(company_id)
        applicable_rules = self._get_applicable_rules(user=user, company=company)
        if not applicable_rules:
            return ((), ())
        lines = self.env['simplify.access.view'].sudo().with_context(
            **{SIMPLIFY_ACCESS_BYPASS_KEY: True}
        ).search([
            ('access_rule_id', 'in', applicable_rules.ids),
            ('model_name', '=', model_name),
            ('active', '=', True),
        ])
        view_ids = tuple(line.view_id.id for line in lines if line.view_id)
        view_types = tuple(line.view_type for line in lines if line.view_type)
        return (view_ids, view_types)

    @api.model
    def get_hidden_action_ids(self, user=None, company=None):
        """Return {'act_window': set(...), 'server': set(...),
        'client': set(...)} - action ids hidden for `user` in `company`,
        not scoped to any particular model (an action can be bound to
        several models, or none).
        """
        user = user or self.env.user
        company = company or self.env.company
        if self._is_bypass_user(user=user):
            return {'act_window': set(), 'server': set(), 'client': set()}
        act_window_ids, server_ids, client_ids = self._get_hidden_action_ids_cached(
            user.id, company.id,
        )
        return {
            'act_window': set(act_window_ids),
            'server': set(server_ids),
            'client': set(client_ids),
        }

    @ormcache('user_id', 'company_id')
    def _get_hidden_action_ids_cached(self, user_id, company_id):
        user = self.env['res.users'].sudo().browse(user_id)
        company = self.env['res.company'].sudo().browse(company_id)
        applicable_rules = self._get_applicable_rules(user=user, company=company)
        if not applicable_rules:
            return ((), (), ())
        lines = self.env['simplify.access.action'].sudo().with_context(
            **{SIMPLIFY_ACCESS_BYPASS_KEY: True}
        ).search([
            ('access_rule_id', 'in', applicable_rules.ids),
            ('active', '=', True),
        ])
        act_window_ids = tuple(
            line.act_window_id.id for line in lines
            if line.action_type == 'act_window' and line.act_window_id
        )
        server_ids = tuple(
            line.server_action_id.id for line in lines
            if line.action_type == 'server' and line.server_action_id
        )
        client_ids = tuple(
            line.client_action_id.id for line in lines
            if line.action_type == 'client' and line.client_action_id
        )
        return (act_window_ids, server_ids, client_ids)

    @api.model
    def get_hidden_report_ids(self, user=None, company=None):
        """Return the set of ir.actions.report ids hidden for `user` in
        `company`.
        """
        user = user or self.env.user
        company = company or self.env.company
        if self._is_bypass_user(user=user):
            return set()
        return set(self._get_hidden_report_ids_cached(user.id, company.id))

    @ormcache('user_id', 'company_id')
    def _get_hidden_report_ids_cached(self, user_id, company_id):
        user = self.env['res.users'].sudo().browse(user_id)
        company = self.env['res.company'].sudo().browse(company_id)
        applicable_rules = self._get_applicable_rules(user=user, company=company)
        if not applicable_rules:
            return ()
        lines = self.env['simplify.access.report'].sudo().with_context(
            **{SIMPLIFY_ACCESS_BYPASS_KEY: True}
        ).search([
            ('access_rule_id', 'in', applicable_rules.ids),
            ('active', '=', True),
        ])
        return tuple(line.report_id.id for line in lines)

    # ------------------------------------------------------------------
    # Phase 7 - Global Access & Chatter policy
    # ------------------------------------------------------------------
    _GLOBAL_POLICY_FIELDS = (
        'global_readonly',
        'hide_import', 'hide_export', 'hide_archive', 'hide_unarchive',
        'hide_duplicate',
        'disable_login', 'disable_developer_mode',
        'restrict_module_install', 'restrict_module_upgrade',
        'restrict_module_uninstall',
        'hide_chatter', 'disable_send_message', 'disable_log_note',
        'disable_activities',
    )

    @api.model
    def get_global_policy(self, user=None, company=None):
        """Return the effective Phase 7 global/chatter policy for `user`
        (defaults to current user) in `company` (defaults to current
        company) - a flat dict of all _GLOBAL_POLICY_FIELDS, each
        combined with OR across every applicable rule (most restrictive
        wins, same combination rule as every other boolean policy in
        this module).

        Not scoped to any particular model - these are global
        restrictions by definition.

        Bypass users (SUPERUSER, internal bypass context, Access
        Management Managers) always get an all-False policy.
        """
        user = user or self.env.user
        company = company or self.env.company

        effective_policy = {field: False for field in self._GLOBAL_POLICY_FIELDS}
        if self._is_bypass_user(user=user):
            return effective_policy

        flags = self._get_global_policy_cached(user.id, company.id)
        for field, value in zip(self._GLOBAL_POLICY_FIELDS, flags):
            effective_policy[field] = bool(value)
        return effective_policy

    @ormcache('user_id', 'company_id')
    def _get_global_policy_cached(self, user_id, company_id):
        user = self.env['res.users'].sudo().browse(user_id)
        company = self.env['res.company'].sudo().browse(company_id)
        applicable_rules = self._get_applicable_rules(user=user, company=company)
        if not applicable_rules:
            return tuple(False for _ in self._GLOBAL_POLICY_FIELDS)

        # Rules were already read via _get_applicable_rules() under the
        # internal bypass context, so a plain field read here is safe
        # and needs no further sudo()/context wrapping.
        combined = {field: False for field in self._GLOBAL_POLICY_FIELDS}
        for rule in applicable_rules:
            for field in self._GLOBAL_POLICY_FIELDS:
                if rule[field]:
                    combined[field] = True

        return tuple(combined[field] for field in self._GLOBAL_POLICY_FIELDS)

    @api.model
    def is_login_disabled_for_user(self, user):
        """Return True if ANY applicable Access Rule disables login for
        `user`, checked across EVERY company `user` is allowed to
        operate in (user.company_ids) - not just a single "current"
        company, since there is no meaningful active-company context
        before authentication succeeds (Phase 7 section 30). A rule
        scoped to a specific company still blocks login if that company
        is among the user's allowed companies; apply_all_companies
        rules block regardless.

        Bypass users (SUPERUSER, Access Management Managers) are never
        blocked, via the same _is_bypass_user() used everywhere else.
        """
        if self._is_bypass_user(user=user):
            return False
        companies = user.sudo().company_ids or user.sudo().company_id
        for company in companies:
            policy = self.get_global_policy(user=user, company=company)
            if policy.get('disable_login'):
                return True
        return False

    # ------------------------------------------------------------------
    # Central cache invalidation hook
    # ------------------------------------------------------------------
    @api.model
    def clear_caches(self):
        """Single, central entry point for invalidating Simplify Access
        Management policy caches.

        This clears the registry-level ORM cache via
        ``self.env.registry.clear_cache()``, which is the current Odoo 19
        supported mechanism for invalidating ormcache-backed methods
        (including ``_get_hidden_menu_ids_cached``, the one cached policy
        method this module currently has).

        A previous implementation tried
        ``self._get_hidden_menu_ids_cached.clear_cache(self)`` (calling
        ``clear_cache`` directly on the decorated function object), which
        raised ``AttributeError: 'function' object has no attribute
        'clear_cache'`` in this Odoo 19 environment - that per-function
        attribute is not what Odoo 19 exposes here. The registry-level
        call below is the safer, centrally-supported replacement.

        This only clears the ORM's own method cache, scoped to this
        registry/database - it does not restart the registry, does not
        touch unrelated application state, and is only ever called after
        a successful create/write/unlink of Simplify Access Management
        configuration records (simplify.access.rule,
        simplify.access.model, simplify.access.menu) - never on every
        request or every menu load.

        simplify.access.rule and simplify.access.menu both call this one
        method. If a future phase adds more cached policy methods, no
        change is needed here - a registry cache clear covers all of
        them.
        """
        self.env.registry.clear_cache()
        return True
