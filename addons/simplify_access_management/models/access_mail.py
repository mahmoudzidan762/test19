# -*- coding: utf-8 -*-
from odoo import _, api, models
from odoo.exceptions import AccessError

from .access_policy import SIMPLIFY_ACCESS_BYPASS_KEY


class MailThread(models.AbstractModel):
    """Backend enforcement for Phase 7 chatter restrictions
    (disable_send_message / disable_log_note).

    ``mail.thread`` is the standard Odoo mixin any model inherits to get
    chatter functionality; this module already depends on ``mail``, so
    extending it here is safe and does not introduce a new dependency.

    ASSUMPTION FLAGGED FOR MANUAL VERIFICATION: distinguishing a "Log
    Note" from a regular "Send Message" purely from message_post()'s
    keyword arguments (checking `subtype_xmlid` for the native
    "mail.mt_note" subtype, vs. anything else defaulting to a regular
    message) was not verified against local Odoo 19 source. If the
    caller passes neither, this defaults to treating the post as a
    regular message (checked against disable_send_message) - the safer
    default, since log notes are a strict subset of message_post() calls
    (an explicit, deliberate choice by the caller), not the default
    behavior.

    message_post(**kwargs) itself (not a fixed positional signature) is
    used defensively here since exact keyword names have shifted across
    Odoo versions historically - this override only inspects `kwargs`,
    it never changes what is forwarded to super().
    """
    _inherit = 'mail.thread'

    def message_post(self, **kwargs):
        self._simplify_check_message_post_access(kwargs)
        return super().message_post(**kwargs)

    def _simplify_check_message_post_access(self, kwargs):
        # SECURITY FIX (Phase 8 audit): a standalone bypass-context
        # check used to sit here - a critical, externally-spoofable
        # vulnerability (see models/access_enforcement.py's
        # _simplify_enforcement_skipped() docstring for the full
        # rationale). The self.env.su check below already correctly and
        # safely covers every legitimate internal/system use case on
        # its own.
        if self.env.su:
            # Automated system emails, cron-generated notifications, and
            # any other sudo()-elevated internal posting must never be
            # blocked by a restriction meant for the ordinary,
            # non-elevated actions of a targeted human user (Phase 7
            # section 13: "Do NOT block automated system emails,
            # cron-generated emails, sudo/system processes").
            return

        policy_helper = self.env['simplify.access.policy'].sudo().with_context(
            **{SIMPLIFY_ACCESS_BYPASS_KEY: True}
        )
        global_policy = policy_helper.get_global_policy(
            user=self.env.user, company=self.env.company,
        )
        if not (global_policy.get('disable_send_message')
                or global_policy.get('disable_log_note')):
            return

        subtype_xmlid = kwargs.get('subtype_xmlid') or ''
        is_log_note = 'note' in subtype_xmlid

        if is_log_note and global_policy.get('disable_log_note'):
            raise AccessError(_(
                'You are not allowed to post log notes.'
            ))
        if not is_log_note and global_policy.get('disable_send_message'):
            raise AccessError(_(
                'You are not allowed to send messages.'
            ))


class MailActivity(models.Model):
    """Backend enforcement for Phase 7 disable_activities.

    ASSUMPTION FLAGGED FOR MANUAL VERIFICATION: create() here follows
    the same @api.model_create_multi + create(self, vals_list) pattern
    already used (and documented) throughout this module for every
    other model - see models/access_enforcement.py's create() for the
    full assumption note, which applies identically here.
    """
    _inherit = 'mail.activity'

    @api.model_create_multi
    def create(self, vals_list):
        self._simplify_check_activity_create_access()
        return super().create(vals_list)

    def _simplify_check_activity_create_access(self):
        # SECURITY FIX (Phase 8 audit): a standalone bypass-context
        # check used to sit here - see the message_post check above
        # (same file) and _simplify_enforcement_skipped()'s docstring
        # in models/access_enforcement.py for the full rationale.
        if self.env.su:
            # System/automation-generated activities (e.g. scheduled
            # follow-ups created by other modules under sudo()) must
            # never be blocked - Phase 7 section 15.
            return
        policy_helper = self.env['simplify.access.policy'].sudo().with_context(
            **{SIMPLIFY_ACCESS_BYPASS_KEY: True}
        )
        global_policy = policy_helper.get_global_policy(
            user=self.env.user, company=self.env.company,
        )
        if global_policy.get('disable_activities'):
            raise AccessError(_(
                'You are not allowed to create activities.'
            ))
