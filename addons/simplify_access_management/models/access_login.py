# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, models
from odoo.exceptions import AccessDenied


class ResUsers(models.Model):
    """Phase 7 disable_login enforcement.

    Overrides ``_check_credentials(self, credential, env)`` - CONFIRMED
    by the user against their actual Odoo 19 installation to be the
    correct authentication hook, called on the res.users record matching
    the login attempt, receiving `credential` (a dict, e.g. `{'login':
    ..., 'password': ..., 'type': 'password'}`) and `env`, and expected
    to return the `auth_info` dict produced by super() (e.g. `{'uid':
    ..., 'auth_method': ..., 'mfa': ...}`) - NOT True/False, NOT None.

    BUG FIXED: the previous version called
    ``super()._check_credentials(credential, env)`` but discarded its
    return value and had no ``return`` statement at all, so the method
    implicitly returned ``None`` on every single successful
    authentication - breaking every login unconditionally, regardless of
    whether any Simplify Access rule was even active. This is now
    corrected: the native `auth_info` is captured and returned exactly
    as produced by super(), whether or not any Simplify check runs.

    Ordering: native credential validation (password/key/etc. actually
    being correct) always runs FIRST via super(). Only if that already
    succeeded does the Simplify disable_login check run - a wrong
    password still fails exactly as it always did, completely unrelated
    to and unaffected by this override.

    Recursion/sudo safety (does NOT reuse the generic env.su-based
    business-operation bypass): resolving whether login is disabled for
    `self` never checks ``self.env.su`` - Odoo's authentication flow may
    itself run with an elevated/sudo environment, and blindly treating
    that as "this user is exempt" would make disable_login never able to
    fire at all. Only two things exempt a user from this check: being
    SUPERUSER, and Access Management Manager membership - both resolved
    via the existing, shared ``_is_bypass_user()``/
    ``is_login_disabled_for_user()`` in simplify.access.policy, not
    duplicated here. The lookup itself is a small number of plain field
    reads/searches on simplify.access.rule (see
    simplify.access.policy.get_global_policy()/_get_applicable_rules())
    - it does not call get_views(), does not load menus, does not touch
    business record searches, and does not depend on any active-company
    web-client state, since none of that exists yet at authentication
    time. Company scope for this specific check is resolved by iterating
    every company the user belongs to (see
    is_login_disabled_for_user()), not a "currently active" company.

    No error-swallowing here on purpose: if resolving the policy raises
    a genuine bug, it surfaces as a real exception rather than being
    silently treated as "login allowed" - masking a real defect behind a
    safety net that would only hide problems like the one just described
    above is worse than a visible failure.
    """
    _inherit = 'res.users'

    def _check_credentials(self, credential, env):
        auth_info = super()._check_credentials(credential, env)
        self._simplify_check_login_allowed()
        return auth_info

    def _simplify_check_login_allowed(self):
        if self.id == SUPERUSER_ID:
            return
        policy = self.env['simplify.access.policy'].sudo().with_context(
            simplify_access_bypass=True
        )
        if policy.is_login_disabled_for_user(self.sudo()):
            # Generic, non-specific failure (Phase 7 section 18): never
            # reveal that a Simplify Access rule specifically caused
            # this, matching Odoo's own generic invalid-credentials
            # wording so a restricted login attempt is indistinguishable
            # from a wrong password to anyone observing it.
            raise AccessDenied()
