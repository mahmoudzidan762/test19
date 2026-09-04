# -*- coding: utf-8 -*-
from odoo import models

from .access_policy import SIMPLIFY_ACCESS_BYPASS_KEY


class IrUiMenu(models.Model):
    """Dynamic, per-user menu visibility restriction (Phase 3).

    Architecture note
    ------------------
    This is normal Odoo model inheritance (``_inherit = 'ir.ui.menu'``),
    NOT monkey patching, and does NOT modify Odoo core or any stored
    ir.ui.menu record (active, groups_id and parent_id are never written
    here). Visibility is recomputed dynamically on every call, so the
    same menu can be visible for User B while hidden for User A at the
    same time.

    ASSUMPTION FLAGGED FOR MANUAL VERIFICATION: this module was built
    without access to the local Odoo 19 source. ``_visible_menu_ids`` is
    the method ir.ui.menu has used for several major versions to compute
    the set of menu ids visible to the current user (consumed by the web
    client's menu-loading endpoint), evaluated AFTER native group-based
    and action-based visibility. Please confirm this method still exists
    with this name/signature in your Odoo 19 checkout before relying on
    this beyond your own testing. If the signature has changed, this
    override will raise a clear error on first use (fails loudly, not
    silently) rather than silently granting or hiding menus incorrectly.

    Security note
    -------------
    Native Odoo menu visibility (groups, associated action availability)
    is always computed first via ``super()``. This override can only
    REMOVE ids from that native result - it can never add a menu that
    Odoo itself would not already show. Underlying model access is never
    touched by this file; see Phase 2 (models/access_enforcement.py) for
    actual model-level security.
    """
    _inherit = 'ir.ui.menu'

    def _visible_menu_ids(self, debug=False):
        visible_menu_ids = super()._visible_menu_ids(debug=debug)

        # SECURITY FIX (Phase 8 audit): a standalone bypass-context
        # check used to sit here - a critical, externally-spoofable
        # vulnerability (see models/access_enforcement.py's
        # _simplify_enforcement_skipped() docstring for the full
        # rationale). self.env.su correctly and safely covers every
        # legitimate internal/system use case on its own, since every
        # internal policy read in this module pairs .sudo() with this
        # context key.
        if self.env.su:
            return visible_menu_ids

        policy = self.env['simplify.access.policy'].sudo().with_context(
            **{SIMPLIFY_ACCESS_BYPASS_KEY: True}
        )
        hidden_menu_ids = policy.get_hidden_menu_ids(
            user=self.env.user, company=self.env.company,
        )
        if not hidden_menu_ids:
            return visible_menu_ids

        filtered_menu_ids = set(visible_menu_ids) - hidden_menu_ids
        filtered_menu_ids = self._simplify_prune_empty_parents(filtered_menu_ids)
        return filtered_menu_ids

    def _simplify_prune_empty_parents(self, menu_ids):
        """Drop parent menus left with no visible children and no action
        of their own, after Simplify's additional restrictions were
        subtracted - so hiding the only child of a parent does not leave
        a useless empty parent behind (mirrors Odoo's own preference for
        not showing empty menus).

        Only touches the already-small `menu_ids` set already produced
        above; no extra per-menu queries beyond a single batched browse/
        read, and the fixed-point loop is bounded by menu tree depth
        (a handful of iterations at most in practice).
        """
        if not menu_ids:
            return menu_ids

        bypass_context = {SIMPLIFY_ACCESS_BYPASS_KEY: True}
        menus = self.sudo().with_context(**bypass_context).browse(menu_ids)
        # menu id -> (parent_id or False, has_own_action)
        menu_info = {
            menu.id: (menu.parent_id.id if menu.parent_id else False, bool(menu.action))
            for menu in menus
        }

        children_count = {}
        for menu_id, (parent_id, _has_action) in menu_info.items():
            if parent_id:
                children_count[parent_id] = children_count.get(parent_id, 0) + 1

        result = set(menu_ids)
        changed = True
        while changed:
            changed = False
            for menu_id in list(result):
                parent_id, has_action = menu_info.get(menu_id, (False, True))
                if has_action:
                    continue
                if children_count.get(menu_id, 0) > 0:
                    continue
                # No action of its own and no visible children left in the
                # filtered set -> this parent is now useless, drop it.
                result.discard(menu_id)
                if parent_id and parent_id in children_count:
                    children_count[parent_id] -= 1
                changed = True

        return result
