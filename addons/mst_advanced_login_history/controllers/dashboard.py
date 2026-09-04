# -*- coding: utf-8 -*-

from odoo import http, fields
from odoo.http import request
from odoo.exceptions import AccessError


class AdvancedLoginHistoryDashboardController(http.Controller):

    def _format_datetime(self, datetime_value):
        if not datetime_value:
            return ""

        user_tz_datetime = fields.Datetime.context_timestamp(
            request.env.user,
            datetime_value
        )
        return user_tz_datetime.strftime("%b %d, %Y %I:%M %p")

    def _format_duration(self, duration):
        if not duration:
            return "-"

        total_minutes = int(duration * 60)
        hours = total_minutes // 60
        minutes = total_minutes % 60

        if hours and minutes:
            return "%sh %sm" % (hours, minutes)

        if hours:
            return "%sh" % hours

        return "%sm" % minutes

    def _get_location_text(self, record):
        location_values = []

        if record.city:
            location_values.append(record.city)

        if record.country:
            location_values.append(record.country)

        if location_values:
            return ", ".join(location_values)

        return record.full_location or "-"

    def _get_device_text(self, record):
        device_values = []

        if record.browser:
            device_values.append(record.browser)

        if record.operating_system:
            device_values.append(record.operating_system)

        if device_values:
            return " / ".join(device_values)

        return "-"

    def _get_country_flag(self, country):
        country = (country or "").strip()

        country_map = {
            "India": "🇮🇳",
            "United States": "🇺🇸",
            "United States of America": "🇺🇸",
            "USA": "🇺🇸",
            "US": "🇺🇸",
            "United Kingdom": "🇬🇧",
            "UK": "🇬🇧",
            "Russia": "🇷🇺",
            "United Arab Emirates": "🇦🇪",
            "UAE": "🇦🇪",
            "Canada": "🇨🇦",
            "Australia": "🇦🇺",
            "Germany": "🇩🇪",
            "France": "🇫🇷",
            "Singapore": "🇸🇬",
            "Malaysia": "🇲🇾",
            "Sri Lanka": "🇱🇰",
            "China": "🇨🇳",
            "Japan": "🇯🇵",
            "South Korea": "🇰🇷",
            "Brazil": "🇧🇷",
            "Mexico": "🇲🇽",
            "South Africa": "🇿🇦",
            "Saudi Arabia": "🇸🇦",
            "Qatar": "🇶🇦",
            "Oman": "🇴🇲",
            "Kuwait": "🇰🇼",
        }

        return country_map.get(country, "🌍")

    def _get_browser_icon(self, browser):
        browser = (browser or "").lower()

        if "chrome" in browser or "chromium" in browser:
            return "fa-chrome"

        if "firefox" in browser:
            return "fa-firefox"

        if "edge" in browser:
            return "fa-edge"

        if "safari" in browser:
            return "fa-safari"

        if "opera" in browser:
            return "fa-opera"

        return "fa-globe"

    def _get_os_icon(self, operating_system):
        os_name = (operating_system or "").lower()

        if "windows" in os_name:
            return "fa-windows"

        if "linux" in os_name or "ubuntu" in os_name:
            return "fa-linux"

        if "android" in os_name:
            return "fa-android"

        if "mac" in os_name or "ios" in os_name or "iphone" in os_name or "ipad" in os_name:
            return "fa-apple"

        return "fa-desktop"

    def _get_browser_name(self, record):
        browser = record.browser or "-"

        browser_map = {
            "chrome": "Chrome",
            "firefox": "Firefox",
            "edge": "Edge",
            "safari": "Safari",
            "opera": "Opera",
            "chromium": "Chromium",
        }

        browser_lower = browser.lower()

        for key, value in browser_map.items():
            if key in browser_lower:
                return value

        return browser

    def _get_os_name(self, record):
        os_name = record.operating_system or ""

        os_map = {
            "windows": "Windows",
            "linux": "Linux",
            "ubuntu": "Linux",
            "android": "Android",
            "mac": "macOS",
            "ios": "iOS",
            "iphone": "iOS",
            "ipad": "iOS",
        }

        os_lower = os_name.lower()

        for key, value in os_map.items():
            if key in os_lower:
                return value

        return os_name

    def _prepare_login_row(self, record):
        status_label = "Successful Login"
        status_class = "success"

        if record.status == "logout":
            status_label = "Logout"
            status_class = "logout"

        return {
            "id": "login_%s" % record.id,
            "res_model": "login.history",
            "res_id": record.id,
            "user": record.user_id.name or "-",
            "email": record.user_id.login or "",
            "login_time": self._format_datetime(record.login_time),
            "raw_date": record.login_time,
            "status": status_label,
            "status_class": status_class,
            "ip_address": record.ip_address or "-",
            "location": self._get_location_text(record),
            "country_flag": self._get_country_flag(record.country),
            "browser_name": self._get_browser_name(record),
            "os_name": self._get_os_name(record),
            "browser_icon": self._get_browser_icon(record.browser),
            "os_icon": self._get_os_icon(record.operating_system),
            "browser_device": self._get_device_text(record),
            "session_duration": self._format_duration(record.duration),
            "latitude": record.latitude or "",
            "longitude": record.longitude or "",
            "map_url": record.map_url or "",
        }

    def _prepare_failed_row(self, record):
        return {
            "id": "failed_%s" % record.id,
            "res_model": "login.failed.history",
            "res_id": record.id,
            "user": record.login or "Unknown User",
            "email": record.login or "",
            "login_time": self._format_datetime(record.attempt_time),
            "raw_date": record.attempt_time,
            "status": "Failed Login",
            "status_class": "failed",
            "ip_address": record.ip_address or "-",
            "location": self._get_location_text(record),
            "country_flag": self._get_country_flag(record.country),
            "browser_name": self._get_browser_name(record),
            "os_name": self._get_os_name(record),
            "browser_icon": self._get_browser_icon(record.browser),
            "os_icon": self._get_os_icon(record.operating_system),
            "browser_device": self._get_device_text(record),
            "session_duration": "-",
            "latitude": record.latitude or "",
            "longitude": record.longitude or "",
            "map_url": record.map_url or "",
        }

    def _prepare_latest_location(self, rows):
        for row in rows:
            if row.get("latitude") and row.get("longitude"):
                latitude = row.get("latitude")
                longitude = row.get("longitude")

                return {
                    "location": row.get("location") or "-",
                    "country_flag": row.get("country_flag") or "🌍",
                    "ip_address": row.get("ip_address") or "-",
                    "browser_device": row.get("browser_device") or "-",
                    "browser_name": row.get("browser_name") or "-",
                    "os_name": row.get("os_name") or "",
                    "browser_icon": row.get("browser_icon") or "fa-globe",
                    "os_icon": row.get("os_icon") or "fa-desktop",
                    "login_time": row.get("login_time") or "-",
                    "map_embed_url": "https://maps.google.com/maps?q=%s,%s&z=12&output=embed" % (
                        latitude,
                        longitude
                    ),
                    "open_url": "https://www.google.com/maps?q=%s,%s" % (
                        latitude,
                        longitude
                    ),
                }

        return {
            "location": "-",
            "country_flag": "🌍",
            "ip_address": "-",
            "browser_device": "-",
            "browser_name": "-",
            "os_name": "",
            "browser_icon": "fa-globe",
            "os_icon": "fa-desktop",
            "login_time": "-",
            "map_embed_url": "",
            "open_url": "",
        }

    @http.route(
        "/mst_advanced_login_history/dashboard_data",
        type="json",
        auth="user"
    )
    def get_dashboard_data(self):
        if not request.env.user.has_group("base.group_system"):
            raise AccessError("Only administrators can view login dashboard.")

        LoginHistory = request.env["login.history"].sudo()
        FailedHistory = request.env["login.failed.history"].sudo()

        login_records = LoginHistory.search(
            [],
            order="login_time desc",
            limit=20
        )

        failed_records = FailedHistory.search(
            [],
            order="attempt_time desc",
            limit=20
        )

        login_rows = [
            self._prepare_login_row(record)
            for record in login_records
        ]

        failed_rows = [
            self._prepare_failed_row(record)
            for record in failed_records
        ]

        all_rows = login_rows + failed_rows

        all_rows = sorted(
            all_rows,
            key=lambda row: row.get("raw_date") or fields.Datetime.now(),
            reverse=True
        )[:20]

        active_user_ids = LoginHistory.search([
            ("status", "=", "active")
        ]).mapped("user_id").ids

        total_logins = LoginHistory.search_count([])
        successful_logins = LoginHistory.search_count([
            ("user_id", "!=", False)
        ])        
        failed_attempts = FailedHistory.search_count([])
        active_users = len(set(active_user_ids))

        latest_location = self._prepare_latest_location(all_rows)

        for row in all_rows:
            row.pop("raw_date", None)

        recent_activity = all_rows[:5]

        return {
            "cards": [
                {
                    "title": "Total Logins",
                    "value": total_logins,
                    "icon": "fa-users",
                    "class": "primary",
                },
                {
                    "title": "Successful",
                    "value": successful_logins,
                    "icon": "fa-check",
                    "class": "success",
                },
                {
                    "title": "Failed Attempts",
                    "value": failed_attempts,
                    "icon": "fa-warning",
                    "class": "danger",
                },
                {
                    "title": "Active Users",
                    "value": active_users,
                    "icon": "fa-user-circle",
                    "class": "purple",
                },
            ],
            "rows": all_rows,
            "location": latest_location,
            "recent_activity": recent_activity,
        }