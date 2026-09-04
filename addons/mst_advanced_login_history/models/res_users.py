# -*- coding: utf-8 -*-

import logging

from odoo import fields, models
from odoo.exceptions import AccessDenied
from odoo.http import request

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = "res.users"

    login_history_ids = fields.One2many(
        comodel_name="login.history",
        inverse_name="user_id",
        string="User Sessions",
        readonly=True,
    )

    activity_log_ids = fields.One2many(
        comodel_name="mst.user.activity.log",
        inverse_name="user_id",
        string="Activity Logs",
        readonly=True,
    )

    def authenticate(self, credential, user_agent_env):
        """
        Odoo 19 compatible authentication override.
        """

        _logger.warning("MST DEBUG: authenticate() method called")

        login = ""

        if isinstance(credential, dict):
            login = credential.get("login") or ""

        _logger.warning("MST DEBUG: Login attempt for login=%s", login)

        try:
            auth_info = super().authenticate(
                credential,
                user_agent_env
            )

        except AccessDenied:
            _logger.warning("MST DEBUG: Failed login detected for login=%s", login)

            self._mst_create_failed_login_history(
                login=login,
                reason="Invalid login credentials"
            )

            raise

        _logger.warning("MST DEBUG: Successful login auth_info=%s", auth_info)

        self._mst_create_success_login_history(auth_info)

        return auth_info

    def _mst_create_failed_login_history(
        self,
        login="",
        reason="Invalid login credentials"
    ):
        try:
            _logger.warning("MST DEBUG: Creating failed login record for %s", login)

            if not request or not request.env:
                _logger.warning("MST DEBUG: request or request.env not available for failed login")
                return True

            request.env["login.failed.history"].sudo().create_failed_login_record(
                login=login,
                reason=reason
            )

            # Important: failed login raises AccessDenied after this.
            # So commit is needed, otherwise failed record may rollback.
            request.env.cr.commit()

            _logger.warning("MST DEBUG: Failed login record created successfully")

        except Exception as error:
            _logger.exception(
                "MST DEBUG: Failed login tracking failed: %s",
                error
            )

        return True

    def _mst_create_success_login_history(self, auth_info):
        try:
            _logger.warning("MST DEBUG: Creating success login record")

            uid = False

            if isinstance(auth_info, dict):
                uid = auth_info.get("uid")

            elif isinstance(auth_info, int):
                uid = auth_info

            _logger.warning("MST DEBUG: Success login uid=%s", uid)

            if not uid:
                _logger.warning("MST DEBUG: No uid found from auth_info")
                return True

            if not request or not request.env:
                _logger.warning("MST DEBUG: request or request.env not available for success login")
                return True

            user = request.env["res.users"].sudo().browse(uid)

            if user.exists():
                request.env["login.history"].sudo().create_login_record(user)
                _logger.warning("MST DEBUG: Success login record created for user=%s", user.login)
            else:
                _logger.warning("MST DEBUG: User not found for uid=%s", uid)

        except Exception as error:
            _logger.exception(
                "MST DEBUG: Successful login tracking failed: %s",
                error
            )

        return True

    def action_kill_all_sessions(self):
        for user in self:
            active_sessions = self.env["login.history"].sudo().search([
                ("user_id", "=", user.id),
                ("status", "=", "active"),
            ])

            for session_record in active_sessions:
                session_id = session_record.session_id

                if session_id:
                    try:
                        if request and request.session_store:
                            session = request.session_store.get(session_id)

                            if session:
                                request.session_store.delete(session)

                    except Exception as error:
                        _logger.exception(
                            "Failed to delete session %s: %s",
                            session_id,
                            error
                        )

                session_record.write({
                    "logout_time": fields.Datetime.now(),
                    "status": "logout",
                })

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Sessions Killed",
                "message": "All active sessions for this user have been killed.",
                "type": "success",
                "sticky": False,
            },
        }