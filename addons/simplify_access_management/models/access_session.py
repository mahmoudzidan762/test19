# -*- coding: utf-8 -*-
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class IrHttp(models.AbstractModel):
    """Central Simplify Access frontend policy exposure (Phase 7).

    Confirmed working end-to-end against the real Odoo 19 installation
    this module targets, for all five UI-visible flags exposed here.
    Two independent frontend mechanisms consume this same policy dict,
    reading directly from `session.simplify_access_policy` (zero extra
    RPC calls per component):
      * static/src/js/simplify_hide_import.js - cogMenu registry patch
        (hide_import).
      * static/src/js/simplify_list_action_menu.js - ListController
        static action menu patch (hide_export, hide_archive,
        hide_unarchive, hide_duplicate).

    FAIL-SAFE DESIGN: unlike most overrides in this module, a wrong
    assumption here must not corrupt session_info()'s own payload -
    that dict carries core session/auth data (uid, csrf token, company,
    etc.) that the ENTIRE web client depends on to function at all, so
    breaking it would be far more severe than a UI item simply staying
    visible. The added logic is therefore wrapped in its own try/except
    that, on ANY failure, leaves `result` completely untouched and only
    logs a warning - the new key is simply absent in that case, which
    the frontend patch treats as "not restricted" (a safe, fail-open
    default for a UI convenience - the actual security boundary is the
    server-side AccessError raised in models/access_enforcement.py,
    which does not depend on this at all).
    """
    _inherit = 'ir.http'

    def session_info(self):
        result = super().session_info()
        self._simplify_add_frontend_policy(result)
        return result

    def _simplify_add_frontend_policy(self, result):
        if not isinstance(result, dict):
            return
        try:
            policy = self.env['simplify.access.policy'].sudo().with_context(
                simplify_access_bypass=True
            )
            global_policy = policy.get_global_policy(
                user=self.env.user, company=self.env.company,
            )
            result['simplify_access_policy'] = {
                'hide_import': bool(global_policy.get('hide_import')),
                'hide_export': bool(global_policy.get('hide_export')),
                'hide_archive': bool(global_policy.get('hide_archive')),
                'hide_unarchive': bool(global_policy.get('hide_unarchive')),
                'hide_duplicate': bool(global_policy.get('hide_duplicate')),
            }
        except Exception:
            _logger.warning(
                'simplify_access_management: failed to add frontend '
                'policy data to session_info(); the affected UI menu '
                'items will simply remain visible for this session (UI '
                'convenience only - server-side enforcement is '
                'unaffected).', exc_info=True,
            )
