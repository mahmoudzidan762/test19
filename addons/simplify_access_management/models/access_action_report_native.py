# -*- coding: utf-8 -*-
import logging

from odoo import _, api, models
from odoo.exceptions import AccessError

from .access_policy import SIMPLIFY_ACCESS_BYPASS_KEY

_logger = logging.getLogger(__name__)


class IrActionsActions(models.Model):
    """UI-level filtering of the Action/Print ("more") menu (Phase 6).

    ASSUMPTION FLAGGED FOR MANUAL VERIFICATION: ``get_bindings(self,
    model_name)`` is, to my knowledge, the long-standing method
    ``ir.actions.actions`` exposes to populate the web client's
    contextual action/print dropdown for a given model, returning a
    dict such as ``{'action': [...], 'report': [...]}`` of action-like
    dicts. This was NOT verified against local Odoo 19 source (no
    server/source access in this environment - see the repeated notes
    throughout this module). To keep the blast radius of a wrong
    assumption small - this can be called for many models - the
    filtering logic below is entirely wrapped in a try/except that logs
    a warning and returns the native, unmodified bindings on any
    failure (unexpected key names, unexpected entry shapes, etc.) rather
    than breaking the action/print menu for everyone.
    """
    _inherit = 'ir.actions.actions'

    @api.model
    def get_bindings(self, model_name):
        result = super().get_bindings(model_name)
        self._simplify_filter_bindings(result, model_name)
        return result

    def _simplify_filter_bindings(self, result, model_name):
        if self._simplify_enforcement_skipped():
            return
        if not isinstance(result, dict):
            return
        try:
            policy = self.env['simplify.access.policy'].sudo().with_context(
                **{SIMPLIFY_ACCESS_BYPASS_KEY: True}
            )
            hidden_action_ids = policy.get_hidden_action_ids(
                user=self.env.user, company=self.env.company,
            )
            all_hidden_action_ids = set()
            for id_set in hidden_action_ids.values():
                all_hidden_action_ids |= id_set
            hidden_report_ids = policy.get_hidden_report_ids(
                user=self.env.user, company=self.env.company,
            )
            if not all_hidden_action_ids and not hidden_report_ids:
                return

            for key in ('action', 'report'):
                entries = result.get(key)
                if not isinstance(entries, list):
                    continue
                hidden_ids = hidden_report_ids if key == 'report' else all_hidden_action_ids
                result[key] = [
                    entry for entry in entries
                    if not (isinstance(entry, dict) and entry.get('id') in hidden_ids)
                ]
        except Exception:
            _logger.warning(
                'simplify_access_management: failed to apply Phase 6 '
                'action/report binding restrictions for model %s; '
                'returning native bindings unmodified as a safe '
                'fallback.', model_name, exc_info=True,
            )


class IrActionsServer(models.Model):
    """Backend enforcement for restricted Server Actions (Phase 6).

    ASSUMPTION FLAGGED FOR MANUAL VERIFICATION: ``run(self)`` - no other
    arguments beyond self, returning an action dict or None/False - has
    been the long-standing execution entrypoint for
    ``ir.actions.server``. This is one of the more stable methods
    touched in this build (simpler signature, less version churn than
    view/export methods), but was still not verified against local
    Odoo 19 source.
    """
    _inherit = 'ir.actions.server'

    def run(self):
        self._simplify_check_server_action_access()
        return super().run()

    def _simplify_check_server_action_access(self):
        if self._simplify_enforcement_skipped():
            return
        if not self:
            return
        policy = self.env['simplify.access.policy'].sudo().with_context(
            **{SIMPLIFY_ACCESS_BYPASS_KEY: True}
        )
        hidden_action_ids = policy.get_hidden_action_ids(
            user=self.env.user, company=self.env.company,
        )
        forbidden_ids = hidden_action_ids.get('server') or set()
        if not forbidden_ids:
            return
        if any(record.id in forbidden_ids for record in self):
            raise AccessError(_(
                'You are not allowed to execute this action.'
            ))


class IrActionsReport(models.Model):
    """Backend enforcement for restricted Reports (Phase 6).

    ASSUMPTION FLAGGED FOR MANUAL VERIFICATION AND KNOWN LIMITATION:
    ``_render`` was chosen as a best-effort central dispatch point for
    report generation, based on recent Odoo versions - but was NOT
    verified against local Odoo 19 source, and report rendering also
    has an HTTP controller entry point (the ``/report/...`` download
    URL) that this module cannot see or verify at all, since it has no
    visibility into Odoo's controller routing layer for this version.
    This ORM-level check therefore covers RPC/ORM-driven report
    generation with reasonably high confidence, but coverage of the
    direct HTTP download URL specifically depends on whether that
    controller ultimately calls through this same method before
    producing output - please verify this specifically (see Manual
    Tests, Test F: "Direct execution").

    To avoid the severe blast radius of breaking ALL report generation
    for ALL users if the assumed signature/self-binding is wrong, the
    added check is wrapped in its own try/except: if it cannot
    confidently resolve which report is being rendered, it logs a
    warning and lets the render proceed via super() unchanged - this
    degrades to "not enforced for this specific call shape" rather than
    "every report is broken".
    """
    _inherit = 'ir.actions.report'

    def _render(self, *args, **kwargs):
        try:
            self._simplify_check_report_render_access()
        except AccessError:
            raise
        except Exception:
            _logger.warning(
                'simplify_access_management: could not resolve report '
                'identity for a _render() call to check Phase 6 report '
                'restrictions; allowing native behaviour for this call.',
                exc_info=True,
            )
        return super()._render(*args, **kwargs)

    def _simplify_check_report_render_access(self):
        if self._simplify_enforcement_skipped():
            return
        if not self:
            return
        policy = self.env['simplify.access.policy'].sudo().with_context(
            **{SIMPLIFY_ACCESS_BYPASS_KEY: True}
        )
        hidden_report_ids = policy.get_hidden_report_ids(
            user=self.env.user, company=self.env.company,
        )
        if not hidden_report_ids:
            return
        if any(record.id in hidden_report_ids for record in self):
            raise AccessError(_(
                'You are not allowed to generate this report.'
            ))


class IrActionsActWindow(models.Model):
    """Two independent Phase 6 restrictions on ir.actions.act_window,
    both implemented via the same override for the same reason (a
    single, safe, already-confirmed hook where the current action
    record is known, before anything is returned to the caller):

    1. WHOLE-ACTION restriction (this fix, simplify.access.action with
       action_type='act_window'): if the action ITSELF is configured as
       restricted for the current user, raise AccessError before any
       action dictionary is built at all - the user gets a clean denial,
       never a silent fallback to some other view of the same
       underlying model. This is deliberately independent from (2)
       below - restricting one Window Action does not restrict the
       model it opens, nor any OTHER action that also happens to open
       that model; see Phase 2/Phase 5 for actual model/record security.

    2. VIEW-TYPE/specific-view restriction (simplify.access.view):
       filters which view types (Kanban/List/Graph/Pivot/...) this
       (unrestricted) action advertises as available, so a hidden type
       is never offered as a clickable option in the first place.

    ROOT CAUSE (2) FIXES: the original Phase 6 view restriction only
    filtered get_views() results. But the web client decides WHICH
    view-type tabs/icons to render from the ACTION's own ``views``/
    ``view_mode`` fields - NOT from get_views(). So a hidden view type
    still appeared as a clickable option in the UI; clicking it then
    requested that view type, for which get_views() correctly had
    nothing to return - producing a client-side Owl TypeError ("Cannot
    read properties of undefined (reading 'arch')") instead of a clean
    security denial. The fix is to filter the ACTION's advertised views
    BEFORE the client ever builds that switcher UI.

    get_views() itself (Phase 2/4/6, the central ``base``-inherited
    class) is intentionally NOT touched for view-type/view-id hiding -
    it must always be able to return a valid architecture for whatever
    view it is actually asked for. View-type/specific-view hiding is UI
    AVAILABILITY control, not model security; underlying data access
    remains governed by native ACL, native record rules, Phase 2 (model
    access) and Phase 5 (domain access) regardless of this class.

    Overrides ``_get_action_dict(self)`` - confirmed to exist with this
    name on ``ir.actions.act_window`` in this Odoo 19 environment.
    Called per single action record (self bound to one action), so
    `result` here is a single action dict, not a list.

    Never writes to the database - only the dict returned for the
    current request is modified/blocked; the stored action record
    (view_mode, mobile_view_mode, views, view_id) is never touched.
    """
    _inherit = 'ir.actions.act_window'

    def _get_action_dict(self):
        # Action-execution enforcement (this fix) runs FIRST and is
        # deliberately NOT wrapped in the defensive try/except used
        # below for view-type filtering: this is a genuine security
        # denial, not a best-effort UI convenience, and must never be
        # silently swallowed. If this action itself is restricted for
        # the current user, no action dictionary is built or returned
        # at all - super()._get_action_dict() is never even called.
        self._simplify_check_action_execution_access()

        result = super()._get_action_dict()
        self._simplify_filter_action_dict(result)
        return result

    def _simplify_check_action_execution_access(self):
        """Raise AccessError if this Window Action itself (not merely
        one of its view types) is configured as restricted for the
        current user via simplify.access.action (action_type=
        'act_window'). This is a distinct restriction from
        simplify.access.view's view-type/specific-view hiding, which
        stays independent and unaffected - see class docstring above.

        Blocks BOTH normal navigation (the action is never returned, so
        the web client has nothing to open - it does not fall back to
        Kanban/List/Form/etc., since there is no partial action dict to
        fall back from) AND a manually crafted direct RPC/action
        request for this exact action id, since the check happens here,
        at the single point where the action dictionary is assembled,
        before any of it is returned.
        """
        if self._simplify_enforcement_skipped():
            return
        if not self:
            return
        policy = self.env['simplify.access.policy'].sudo().with_context(
            **{SIMPLIFY_ACCESS_BYPASS_KEY: True}
        )
        hidden_action_ids = policy.get_hidden_action_ids(
            user=self.env.user, company=self.env.company,
        )
        # Only the 'act_window' bucket is relevant here - never mixed
        # with 'server' or 'client' action ids, which belong to entirely
        # different models/id spaces.
        forbidden_ids = hidden_action_ids.get('act_window') or set()
        if not forbidden_ids:
            return
        if any(record.id in forbidden_ids for record in self):
            raise AccessError(_(
                'You are not allowed to execute this action.'
            ))

    def _simplify_filter_action_dict(self, result):
        if self._simplify_enforcement_skipped():
            return
        if not isinstance(result, dict):
            return
        try:
            model_name = result.get('res_model') or self.res_model
            if not model_name:
                return
            policy = self.env['simplify.access.policy'].sudo().with_context(
                **{SIMPLIFY_ACCESS_BYPASS_KEY: True}
            )
            view_policy = policy.get_hidden_view_policy(
                model_name, user=self.env.user, company=self.env.company,
            )
            hidden_view_ids = view_policy.get('view_ids') or set()
            hidden_view_types = view_policy.get('view_types') or set()
            if not hidden_view_ids and not hidden_view_types:
                return
            self._simplify_filter_single_action_dict(
                result, hidden_view_ids, hidden_view_types,
            )
        except Exception:
            _logger.warning(
                'simplify_access_management: failed to apply Phase 6 '
                'view-type restrictions to an ir.actions.act_window '
                '_get_action_dict() result (action id=%s); returning '
                'native action data unmodified as a safe fallback.',
                self.id, exc_info=True,
            )

    def _simplify_filter_single_action_dict(self, result, hidden_view_ids,
                                             hidden_view_types):
        """Filter one action's ``views`` (list of [view_id_or_False,
        view_type] pairs), ``view_mode`` and ``mobile_view_mode``
        (comma-separated strings, e.g. "kanban,list,form,graph") in
        place, plus the default ``view_id`` if it points at a now-
        restricted view - all three/four kept mutually consistent, per
        the exact requirement.
        """
        views = result.get('views')
        if isinstance(views, list):
            filtered = [
                pair for pair in views
                if not self._simplify_is_hidden_view_pair(
                    pair, hidden_view_ids, hidden_view_types,
                )
            ]
            if not filtered and views:
                # Fallback safety (Phase 6 section 12/7): never
                # advertise zero views for an action - prefer 'form',
                # else keep the first originally-available entry, and
                # log a warning rather than producing a completely
                # unusable action for this user.
                fallback = self._simplify_pick_fallback_view_pair(views)
                filtered = [fallback] if fallback else [views[0]]
                _logger.warning(
                    'simplify_access_management: Phase 6 configuration '
                    'would hide every available view for action id=%s '
                    '(model=%s) - keeping one fallback view instead of '
                    'producing an unusable action.',
                    result.get('id'), result.get('res_model'),
                )
            result['views'] = filtered

        for mode_key in ('view_mode', 'mobile_view_mode'):
            mode_value = result.get(mode_key)
            if isinstance(mode_value, str) and mode_value:
                modes = [m for m in mode_value.split(',') if m]
                filtered_modes = [m for m in modes if m not in hidden_view_types]
                if not filtered_modes and modes:
                    filtered_modes = [modes[0]]
                result[mode_key] = ','.join(filtered_modes)

        # Default view_id: if the action's explicit primary view
        # override points at a now-restricted id or type, it must not
        # be left as the default (Phase 6 section 6) - clear it to
        # False so Odoo/the client fall back to the first surviving
        # entry in `views` naturally, exactly like it already does for
        # any action with no explicit view_id override.
        default_view = result.get('view_id')
        default_view_id = None
        if isinstance(default_view, (list, tuple)) and default_view:
            default_view_id = default_view[0]
        elif isinstance(default_view, int):
            default_view_id = default_view
        if default_view_id:
            hidden_by_id = default_view_id in hidden_view_ids
            hidden_by_type = False
            if not hidden_by_id:
                view_type = self.env['ir.ui.view'].sudo().browse(default_view_id).type
                hidden_by_type = view_type in hidden_view_types
            if hidden_by_id or hidden_by_type:
                result['view_id'] = False

    def _simplify_is_hidden_view_pair(self, pair, hidden_view_ids, hidden_view_types):
        try:
            view_id, view_type = pair[0], pair[1]
        except (TypeError, IndexError):
            return False
        if view_type in hidden_view_types:
            return True
        if view_id and view_id in hidden_view_ids:
            return True
        return False

    def _simplify_pick_fallback_view_pair(self, views):
        for pair in views:
            try:
                if pair[1] == 'form':
                    return pair
            except (TypeError, IndexError):
                continue
        return views[0] if views else None
