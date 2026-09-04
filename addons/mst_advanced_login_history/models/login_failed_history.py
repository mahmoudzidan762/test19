import logging
import requests

from odoo import models, fields, api
from odoo.http import request


_logger = logging.getLogger(__name__)


class LoginFailedHistory(models.Model):
    _name = 'login.failed.history'
    _description = 'Failed Login History'
    _order = 'attempt_time desc'

    login = fields.Char(
        string='Login / Email',
        readonly=True
    )

    attempt_time = fields.Datetime(
        string='Attempt Time',
        readonly=True,
        default=fields.Datetime.now
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

    reason = fields.Char(
        string='Reason',
        readonly=True
    )

    location_source = fields.Selection(
        [
            ('browser', 'Browser Location'),
            ('ip', 'IP Geo Location'),
        ],
        string='Location Source',
        readonly=True
    )

    def _compute_display_name(self):
        for record in self:
            login_name = record.login or "Unknown Login"

            if record.attempt_time:
                attempt_time = fields.Datetime.context_timestamp(
                    record,
                    record.attempt_time
                ).strftime("%d-%m-%Y %I:%M %p")

                record.display_name = "%s - Failed Login - %s" % (
                    login_name,
                    attempt_time
                )
            else:
                record.display_name = "%s - Failed Login" % login_name

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
                'Failed login IP geo location failed: %s',
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
                'Failed login reverse geo failed: %s',
                error
            )

        return geo_data

    @api.model
    def create_failed_login_record(
        self,
        login='',
        reason='Invalid login credentials'
    ):
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

        return self.sudo().create({
            'login': login,
            'attempt_time': fields.Datetime.now(),
            'ip_address': ip_address,
            'browser': request_details.get('browser'),
            'operating_system': request_details.get('operating_system'),
            'user_agent': request_details.get('user_agent'),
            'country': geo_data.get('country'),
            'region': geo_data.get('region'),
            'city': geo_data.get('city'),
            'latitude': str(latitude or ''),
            'longitude': str(longitude or ''),
            'full_location': geo_data.get('full_location'),
            'map_url': False,
            'location_source': location_source,
            'reason': reason,
        })

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

    
    @api.model
    def create_failed_login_record_from_values(
        self,
        login="",
        reason="Invalid login credentials",
        request_values=None,
    ):
        request_values = request_values or {}

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

        return self.sudo().create({
            "login": login,
            "attempt_time": fields.Datetime.now(),
            "ip_address": ip_address,
            "browser": request_values.get("browser"),
            "operating_system": request_values.get("operating_system"),
            "user_agent": request_values.get("user_agent"),
            "country": geo_data.get("country"),
            "region": geo_data.get("region"),
            "city": geo_data.get("city"),
            "latitude": str(latitude or ""),
            "longitude": str(longitude or ""),
            "full_location": geo_data.get("full_location"),
            "location_source": location_source,
            "reason": reason,
        })    