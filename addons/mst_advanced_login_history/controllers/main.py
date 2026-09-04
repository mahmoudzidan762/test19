import json

from odoo import http
from odoo.http import request


class LoginHistoryController(http.Controller):

    @http.route(
        '/mst_advanced_login_history/save_guest_location',
        type='http',
        auth='public',
        methods=['POST'],
        csrf=False
    )
    def save_guest_location(self, **kwargs):
        """
        Save browser location before login.
        This works from the login page also.
        """

        try:
            data = {}

            if request.httprequest.data:
                data = json.loads(
                    request.httprequest.data.decode('utf-8')
                )

            latitude = data.get('latitude')
            longitude = data.get('longitude')

            if latitude and longitude:
                request.session['advanced_login_latitude'] = str(latitude)
                request.session['advanced_login_longitude'] = str(longitude)

        except Exception:
            pass

        return request.make_response(
            'success',
            headers=[
                ('Content-Type', 'text/plain')
            ]
        )

    @http.route(
        '/mst_advanced_login_history/update_location',
        type='http',
        auth='user',
        methods=['POST'],
        csrf=False
    )
    def update_location(self, **kwargs):
        """
        Update browser location after login.
        """

        try:
            data = {}

            if request.httprequest.data:
                data = json.loads(
                    request.httprequest.data.decode('utf-8')
                )

            latitude = data.get('latitude')
            longitude = data.get('longitude')

            request.env['login.history'].sudo().update_browser_location(
                latitude=latitude,
                longitude=longitude
            )

        except Exception:
            pass

        return request.make_response(
            'success',
            headers=[
                ('Content-Type', 'text/plain')
            ]
        )

    @http.route(
        '/web/session/logout',
        type='http',
        auth='none',
        csrf=False
    )
    def web_session_logout(self, redirect='/web', **kw):
        """
        Track logout before Odoo destroys session.
        """

        try:
            user_id = request.session.uid
            session_id = request.session.sid

            if user_id:
                request.env['login.history'].sudo().logout_user_record(
                    user_id=user_id,
                    session_id=session_id
                )

        except Exception:
            pass

        request.session.logout(keep_db=True)

        return request.redirect(redirect or '/web')

    @http.route(
        '/mst_advanced_login_history/logout',
        type='http',
        auth='user',
        methods=['POST'],
        csrf=False
    )
    def logout_history(self, **kwargs):
        """
        Optional tab close / browser close logout tracking.
        """

        try:
            request.env['login.history'].sudo().logout_user_record()
        except Exception:
            pass

        return request.make_response(
            'success',
            headers=[
                ('Content-Type', 'text/plain')
            ]
        )