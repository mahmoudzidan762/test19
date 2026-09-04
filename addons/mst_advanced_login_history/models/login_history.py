import logging
import requests

from odoo import models, fields, api
from odoo.http import request


_logger = logging.getLogger(__name__)


class LoginHistory(models.Model):
    _name = 'login.history'
    _description = 'Login History'
    _order = 'login_time desc'

    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        ondelete='cascade'
    )

    login_time = fields.Datetime(
        string='Login Time',
        readonly=True
    )

    logout_time = fields.Datetime(
        string='Logout Time',
        readonly=True
    )

    duration = fields.Float(
        string='Duration (Hours)',
        compute='_compute_duration',
        store=True
    )

    ip_address = fields.Char(
        string='IP Address',
        readonly=True
    )

    browser = fields.Char(
        string='Browser',
        readonly=True
    )

    operating_system = fields.Char(
        string='Operating System',
        readonly=True
    )

    user_agent = fields.Text(
        string='User Agent',
        readonly=True
    )

    session_id = fields.Char(
        string='Session ID',
        readonly=True,
        index=True
    )

    country = fields.Char(
        string='Country',
        readonly=True
    )

    region = fields.Char(
        string='Region',
        readonly=True
    )

    city = fields.Char(
        string='City',
        readonly=True
    )

    latitude = fields.Char(
        string='Latitude',
        readonly=True
    )

    longitude = fields.Char(
        string='Longitude',
        readonly=True
    )

    full_location = fields.Char(
        string='Full Location',
        readonly=True
    )

    map_url = fields.Char(
        string='Map URL',
        compute='_compute_map_url',
        store=True
    )

    location_source = fields.Selection(
        [
            ('browser', 'Browser Location'),
            ('ip', 'IP Geo Location'),
        ],
        string='Location Source',
        readonly=True
    )

    status = fields.Selection(
        [
            ('active', 'Active'),
            ('logout', 'Logout'),
        ],
        string='Status',
        default='active',
        readonly=True,
        index=True
    )
    def _compute_display_name(self):
        for record in self:
            user_name = record.user_id.name or "Unknown User"

            if record.login_time:
                login_time = fields.Datetime.context_timestamp(
                    record,
                    record.login_time
                ).strftime("%d-%m-%Y %I:%M %p")

                record.display_name = "%s - %s" % (
                    user_name,
                    login_time
                )
            else:
                record.display_name = user_name

    @api.depends('login_time', 'logout_time')
    def _compute_duration(self):
        for rec in self:
            rec.duration = 0.0

            if rec.login_time and rec.logout_time:
                delta = rec.logout_time - rec.login_time
                rec.duration = round(delta.total_seconds() / 3600, 4)

    @api.depends('latitude', 'longitude')
    def _compute_map_url(self):
        for rec in self:
            rec.map_url = False

            if rec.latitude and rec.longitude:
                rec.map_url = 'https://www.google.com/maps?q=%s,%s' % (
                    rec.latitude,
                    rec.longitude
                )

    @api.model
    def _get_request_details(self):
        data = {
            'ip_address': '',
            'browser': '',
            'operating_system': '',
            'user_agent': '',
            'session_id': '',
        }

        if not request:
            return data

        http_request = request.httprequest

        if http_request:
            user_agent_string = http_request.headers.get('User-Agent', '')

            data['user_agent'] = user_agent_string

            if http_request.user_agent:
                data['browser'] = http_request.user_agent.browser or user_agent_string
                data['operating_system'] = http_request.user_agent.platform or ''

            ip_address = (
                http_request.headers.get('X-Forwarded-For')
                or http_request.headers.get('X-Real-IP')
                or http_request.remote_addr
                or ''
            )

            if ip_address and ',' in ip_address:
                ip_address = ip_address.split(',')[0].strip()

            data['ip_address'] = ip_address

        if request.session:
            data['session_id'] = request.session.sid or ''

        return data

    @api.model
    def _get_session_browser_location(self):
        location = {
            'latitude': '',
            'longitude': '',
        }

        if request and request.session:
            location['latitude'] = request.session.get(
                'advanced_login_latitude',
                ''
            )
            location['longitude'] = request.session.get(
                'advanced_login_longitude',
                ''
            )

        return location

    @api.model
    def _get_ip_geo_location_data(self, ip_address):
        geo_data = {
            'country': '',
            'region': '',
            'city': '',
            'latitude': '',
            'longitude': '',
            'full_location': '',
        }

        if not ip_address:
            return geo_data

        if ip_address in ['127.0.0.1', 'localhost', '::1']:
            return geo_data

        try:
            response = requests.get(
                'http://ip-api.com/json/%s' % ip_address,
                timeout=5
            )

            if response.status_code == 200:
                result = response.json()

                if result.get('status') == 'success':
                    city = result.get('city', '')
                    region = result.get('regionName', '')
                    country = result.get('country', '')

                    geo_data.update({
                        'country': country,
                        'region': region,
                        'city': city,
                        'latitude': str(result.get('lat', '')),
                        'longitude': str(result.get('lon', '')),
                        'full_location': ', '.join(
                            value for value in [city, region, country] if value
                        ),
                    })

        except Exception as error:
            _logger.exception(
                'IP geo location failed: %s',
                error
            )

        return geo_data

    @api.model
    def _get_reverse_geo_location_data(self, latitude, longitude):
        geo_data = {
            'country': '',
            'region': '',
            'city': '',
            'full_location': '',
        }

        if not latitude or not longitude:
            return geo_data

        try:
            response = requests.get(
                'https://nominatim.openstreetmap.org/reverse',
                params={
                    'format': 'json',
                    'lat': latitude,
                    'lon': longitude,
                    'zoom': 18,
                    'addressdetails': 1,
                },
                headers={
                    'User-Agent': 'advanced-login-history-odoo'
                },
                timeout=8
            )

            if response.status_code == 200:
                result = response.json()
                address = result.get('address', {})

                city = (
                    address.get('city')
                    or address.get('town')
                    or address.get('village')
                    or address.get('county')
                    or ''
                )

                geo_data.update({
                    'country': address.get('country', ''),
                    'region': address.get('state', ''),
                    'city': city,
                    'full_location': result.get('display_name', ''),
                })

        except Exception as error:
            _logger.exception(
                'Reverse geo location failed: %s',
                error
            )

        return geo_data
    @api.model
    def create_login_record_from_values(self, user, request_values):
        if not user:
            return False

        ip_address = request_values.get("ip_address")
        latitude = request_values.get("latitude")
        longitude = request_values.get("longitude")

        location_source = False
        geo_data = {}

        if latitude and longitude:
            geo_data = self._get_reverse_geo_location_data(latitude, longitude)
            location_source = "browser"
        else:
            geo_data = self._get_ip_geo_location_data(ip_address)
            latitude = geo_data.get("latitude")
            longitude = geo_data.get("longitude")
            location_source = "ip" if latitude and longitude else False

        old_records = self.sudo().search([
            ("user_id", "=", user.id),
            ("status", "=", "active"),
        ])

        if old_records:
            old_records.write({
                "logout_time": fields.Datetime.now(),
                "status": "logout",
            })

        return self.sudo().create({
            "user_id": user.id,
            "login_time": fields.Datetime.now(),
            "logout_time": False,
            "ip_address": ip_address,
            "browser": request_values.get("browser"),
            "operating_system": request_values.get("operating_system"),
            "user_agent": request_values.get("user_agent"),
            "session_id": request_values.get("session_id"),
            "country": geo_data.get("country"),
            "region": geo_data.get("region"),
            "city": geo_data.get("city"),
            "latitude": str(latitude or ""),
            "longitude": str(longitude or ""),
            "full_location": geo_data.get("full_location"),
            "location_source": location_source,
            "status": "active",
        })    

    @api.model
    def create_login_record(self, user):
        if not user:
            return False

        request_details = self._get_request_details()
        browser_location = self._get_session_browser_location()

        ip_address = request_details.get('ip_address')

        latitude = browser_location.get('latitude')
        longitude = browser_location.get('longitude')

        location_source = False
        geo_data = {}

        if latitude and longitude:
            geo_data = self._get_reverse_geo_location_data(
                latitude,
                longitude
            )
            location_source = 'browser'
        else:
            geo_data = self._get_ip_geo_location_data(ip_address)
            latitude = geo_data.get('latitude')
            longitude = geo_data.get('longitude')
            location_source = 'ip' if latitude and longitude else False

        old_records = self.sudo().search([
            ('user_id', '=', user.id),
            ('status', '=', 'active'),
        ])

        if old_records:
            old_records.write({
                'logout_time': fields.Datetime.now(),
                'status': 'logout',
            })

        return self.sudo().create({
            'user_id': user.id,
            'login_time': fields.Datetime.now(),
            'logout_time': False,
            'ip_address': ip_address,
            'browser': request_details.get('browser'),
            'operating_system': request_details.get('operating_system'),
            'user_agent': request_details.get('user_agent'),
            'session_id': request_details.get('session_id'),
            'country': geo_data.get('country'),
            'region': geo_data.get('region'),
            'city': geo_data.get('city'),
            'latitude': str(latitude or ''),
            'longitude': str(longitude or ''),
            'full_location': geo_data.get('full_location'),
            'location_source': location_source,
            'status': 'active',
        })

    @api.model
    def update_browser_location(self, latitude=False, longitude=False):
        if not request or not request.session:
            return True

        user_id = request.session.uid
        session_id = request.session.sid

        if not user_id:
            return True

        record = self.sudo().search([
            ('user_id', '=', user_id),
            ('session_id', '=', session_id),
            ('status', '=', 'active'),
        ], order='login_time desc', limit=1)

        if not record:
            record = self.sudo().search([
                ('user_id', '=', user_id),
                ('status', '=', 'active'),
            ], order='login_time desc', limit=1)

        if record and latitude and longitude:
            geo_data = self._get_reverse_geo_location_data(
                latitude,
                longitude
            )

            record.write({
                'latitude': str(latitude),
                'longitude': str(longitude),
                'country': geo_data.get('country') or record.country,
                'region': geo_data.get('region') or record.region,
                'city': geo_data.get('city') or record.city,
                'full_location': geo_data.get('full_location') or record.full_location,
                'location_source': 'browser',
            })

        return True

    @api.model
    def logout_user_record(self, user_id=False, session_id=False):
        current_user_id = user_id
        current_session_id = session_id

        if request and request.session:
            current_user_id = current_user_id or request.session.uid
            current_session_id = current_session_id or request.session.sid

        record = False

        if current_session_id:
            record = self.sudo().search([
                ('session_id', '=', current_session_id),
                ('status', '=', 'active'),
            ], order='login_time desc', limit=1)

        if not record and current_user_id:
            record = self.sudo().search([
                ('user_id', '=', current_user_id),
                ('status', '=', 'active'),
            ], order='login_time desc', limit=1)

        if record:
            record.write({
                'logout_time': fields.Datetime.now(),
                'status': 'logout',
            })

        return True

    def action_open_map(self):
        self.ensure_one()

        if not self.latitude or not self.longitude:
            return False

        return {
            'type': 'ir.actions.act_url',
            'url': 'https://www.google.com/maps?q=%s,%s' % (
                self.latitude,
                self.longitude
            ),
            'target': 'new',
        }