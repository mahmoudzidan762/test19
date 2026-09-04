/** @odoo-module **/

/**
 * Simplify Access Management - List view static action menu items
 * (Phase 7): Export, Duplicate, Archive, Unarchive.
 *
 * CONFIRMED extension point (verified by the user directly against the
 * actual Odoo 19 source, not guessed): these four items are built
 * directly inside ListController.getStaticActionMenuItems() in
 * addons/web/static/src/views/list/list_controller.js, each with its
 * own `isAvailable` function (e.g. duplicate.isAvailable, archive.
 * isAvailable, unarchive.isAvailable, export.isAvailable) - NOT
 * registered in the "cogMenu" registry the way the Import item is (see
 * static/src/js/simplify_hide_import.js, a separate, independent
 * mechanism left untouched).
 *
 * RESTRICTION-ONLY, NEVER GRANTS: for each item, the native
 * `isAvailable` is called first (or treated as available if it doesn't
 * exist), and the Simplify flag can only turn a native "available"
 * result INTO "unavailable" - it can never make an item available that
 * native Odoo would have hidden anyway. This mirrors the exact pattern
 * requested: `!policy.hide_x && (!originalIsAvailable ||
 * originalIsAvailable(...args))`.
 *
 * Reuses the SAME centralized `session.simplify_access_policy` already
 * populated once per page load by models/access_session.py's
 * session_info() override (confirmed working for Import) - no separate
 * policy RPC/service, and no readiness/async handling is needed here:
 * `session` is populated synchronously before any Owl component code
 * runs (it is embedded in the page's initial boot payload), so the
 * policy is already available by the time getStaticActionMenuItems()
 * is first called - there is no race condition to guard against.
 *
 * Archive/Unarchive are kept fully independent, per requirement -
 * hide_archive only ever touches items.archive.isAvailable, and
 * hide_unarchive only ever touches items.unarchive.isAvailable.
 *
 * SAFE REGARDLESS OF OUTCOME: the server-side AccessError enforcement
 * in models/access_enforcement.py (write() for archive/unarchive,
 * copy() for duplicate, export_data() for export) is completely
 * independent of this file and remains fully enforced either way -
 * already confirmed working by the user.
 */

import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";
import { ListController } from "@web/views/list/list_controller";

function getPolicy() {
    return session.simplify_access_policy || {};
}

/**
 * Wrap items[itemKey].isAvailable (if the item exists at all - some
 * models/views may not offer it natively, in which case there is
 * nothing to restrict) so that it additionally requires
 * !policyFlagGetter() alongside whatever native Odoo already decided.
 */
function restrictItemAvailability(items, itemKey, policyFlagGetter) {
    const item = items[itemKey];
    if (!item) {
        return;
    }
    const originalIsAvailable = item.isAvailable;
    item.isAvailable = (...args) => {
        if (policyFlagGetter()) {
            return false;
        }
        return !originalIsAvailable || originalIsAvailable(...args);
    };
}

patch(ListController.prototype, {
    getStaticActionMenuItems() {
        const items = super.getStaticActionMenuItems(...arguments);
        const policy = getPolicy();

        restrictItemAvailability(items, "duplicate", () => !!policy.hide_duplicate);
        restrictItemAvailability(items, "archive", () => !!policy.hide_archive);
        restrictItemAvailability(items, "unarchive", () => !!policy.hide_unarchive);
        restrictItemAvailability(items, "export", () => !!policy.hide_export);

        return items;
    },
});
