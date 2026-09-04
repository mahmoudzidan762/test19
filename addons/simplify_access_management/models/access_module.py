# -*- coding: utf-8 -*-
from odoo import _, models
from odoo.exceptions import AccessError

from .access_policy import SIMPLIFY_ACCESS_BYPASS_KEY


class IrModuleModule(models.Model):
    """Phase 7 module install/upgrade/uninstall backend enforcement.

    Both the "immediate" variants (button_immediate_install/upgrade/
    uninstall - apply right away) and the "mark" variants
    (button_install/upgrade/uninstall - queue the state change for a
    separate Apply step) are covered, since either could be used to
    actually trigger a module state change; blocking only one would
    leave the other as a bypass.

    ASSUMPTION FLAGGED FOR MANUAL VERIFICATION: these six method names
    are believed to be the long-standing public API for module
    management on ir.module.module, called on a recordset with no
    additional arguments beyond self. Not verified against local Odoo
    19 source. A wrong assumption here fails loudly (AttributeError/
    TypeError) the moment a module action is attempted, not silently.

    SUPERUSER is never restricted - guaranteed by construction via
    simplify.access.policy._is_bypass_user()'s own SUPERUSER check,
    reused identically here through get_global_policy(), not
    reimplemented.
    """
    _inherit = 'ir.module.module'

    def button_immediate_install(self):
        self._simplify_check_module_action('restrict_module_install', _('install'))
        return super().button_immediate_install()

    def button_install(self):
        self._simplify_check_module_action('restrict_module_install', _('install'))
        return super().button_install()

    def button_immediate_upgrade(self):
        self._simplify_check_module_action('restrict_module_upgrade', _('upgrade'))
        return super().button_immediate_upgrade()

    def button_upgrade(self):
        self._simplify_check_module_action('restrict_module_upgrade', _('upgrade'))
        return super().button_upgrade()

    def button_immediate_uninstall(self):
        self._simplify_check_module_action('restrict_module_uninstall', _('uninstall'))
        return super().button_immediate_uninstall()

    def button_uninstall(self):
        self._simplify_check_module_action('restrict_module_uninstall', _('uninstall'))
        return super().button_uninstall()

    def _simplify_check_module_action(self, policy_flag, action_label):
        # SECURITY FIX (Phase 8 audit): a standalone bypass-context
        # check used to sit here - see
        # _simplify_enforcement_skipped()'s docstring in
        # models/access_enforcement.py for the full rationale.
        if self.env.su:
            return
        policy_helper = self.env['simplify.access.policy'].sudo().with_context(
            **{SIMPLIFY_ACCESS_BYPASS_KEY: True}
        )
        global_policy = policy_helper.get_global_policy(
            user=self.env.user, company=self.env.company,
        )
        if global_policy.get(policy_flag):
            raise AccessError(_(
                'You are not allowed to %(action)s modules.',
                action=action_label,
            ))
