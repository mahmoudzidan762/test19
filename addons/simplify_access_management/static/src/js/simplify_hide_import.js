/** @odoo-module **/

/**
 * Simplify Access Management - Hide Import cog-menu entry (Phase 7).
 *
 * CONFIRMED WORKING against the real Odoo 19 installation this module
 * targets: the "cogMenu" registry + getEntries() + isDisplayed patching
 * approach correctly hides "Import records" when hide_import=true.
 *
 * SCOPE NOTE: this file previously also attempted to hide Export/
 * Duplicate/Archive/Unarchive via this SAME cogMenu-registry mechanism.
 * That was WRONG - those four items are not registered in the cogMenu
 * registry at all in this Odoo 19 installation; they are built directly
 * inside ListController.getStaticActionMenuItems() (confirmed against
 * actual Odoo 19 source by the user). Those four matchers have been
 * removed from this file entirely (no obsolete/conflicting patches left
 * behind) and re-implemented correctly in
 * static/src/js/simplify_list_action_menu.js, which patches
 * ListController directly instead. This file now handles ONLY Import,
 * exactly as originally confirmed working - untouched otherwise.
 *
 * SAFE REGARDLESS OF OUTCOME: the server-side AccessError in
 * models/access_enforcement.py's load() override is completely
 * independent of this file and remains fully enforced either way.
 */

import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";

const cogMenuRegistry = registry.category("cogMenu");
const patchedComponents = new WeakSet();

function isImportKey(key) {
    return typeof key === "string" && key.toLowerCase().includes("import");
}

function patchImportComponent(key, Component) {
    if (!Component || typeof Component.isDisplayed !== "function") {
        return;
    }
    if (patchedComponents.has(Component)) {
        return;
    }
    patch(Component, {
        isDisplayed(env) {
            const policy = session.simplify_access_policy;
            if (policy && policy.hide_import) {
                return false;
            }
            return super.isDisplayed(env);
        },
    });
    patchedComponents.add(Component);
}

function checkAndPatchImportEntry() {
    try {
        const entries = cogMenuRegistry.getEntries();
        for (const [key, Component] of entries) {
            if (isImportKey(key)) {
                patchImportComponent(key, Component);
            }
        }
    } catch (error) {
        console.error(
            "[Simplify Access] failed to inspect the \"cogMenu\" registry " +
            "for the Import entry. Backend enforcement is unaffected. " +
            "Full error:",
            error
        );
    }
}

checkAndPatchImportEntry();

if (typeof cogMenuRegistry.addEventListener === "function") {
    cogMenuRegistry.addEventListener("UPDATE", checkAndPatchImportEntry);
}
