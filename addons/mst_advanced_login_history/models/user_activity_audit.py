# -*- coding: utf-8 -*-

import json
import logging

from odoo import api, fields, models
from odoo.http import request

_logger = logging.getLogger(__name__)


class MstUserActivityLog(models.Model):
    _name = "mst.user.activity.log"
    _description = "User Activity Log"
    _order = "performed_date desc"

    name = fields.Char(
        string="Record Name",
        readonly=True
    )

    user_id = fields.Many2one(
        "res.users",
        string="User",
        readonly=True,
        index=True
    )

    login = fields.Char(
        string="Login",
        readonly=True
    )

    model_name = fields.Char(
        string="Model",
        readonly=True,
        index=True
    )

    model_description = fields.Char(
        string="Model Description",
        readonly=True
    )

    module_name = fields.Char(
        string="Module",
        readonly=True
    )

    model_config_id = fields.Many2one(
        "mst.activity.log.model.config",
        string="Model Configuration",
        readonly=True,
        index=True
    )

    model_log_enabled = fields.Boolean(
        string="Show in Model Logs",
        readonly=True,
        index=True
    )

    record_id = fields.Integer(
        string="Record ID",
        readonly=True,
        index=True
    )

    action_type = fields.Selection(
        [
            ("create", "Create"),
            ("modify", "Modify"),
            ("delete", "Delete"),
        ],
        string="Action",
        readonly=True,
        index=True
    )

    performed_date = fields.Datetime(
        string="Performed Date",
        default=fields.Datetime.now,
        readonly=True,
        index=True
    )

    session_id = fields.Char(
        string="Session",
        readonly=True,
        index=True
    )

    ip_address = fields.Char(
        string="IP Address",
        readonly=True
    )

    browser = fields.Char(
        string="Browser",
        readonly=True
    )

    operating_system = fields.Char(
        string="Operating System",
        readonly=True
    )

    request_url = fields.Char(
        string="Request URL",
        readonly=True
    )

    request_method = fields.Char(
        string="Request Method",
        readonly=True
    )

    has_changes = fields.Boolean(
        string="Has Changes",
        readonly=True
    )

    has_view_changes = fields.Boolean(
        string="Has View Changes",
        readonly=True
    )

    line_ids = fields.One2many(
        "mst.user.activity.log.line",
        "activity_log_id",
        string="Changes",
        readonly=True
    )

    def action_open_record(self):
        self.ensure_one()

        if self.action_type == "delete":
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Record Deleted",
                    "message": "This record was deleted, so it cannot be opened.",
                    "type": "warning",
                    "sticky": False,
                },
            }

        if not self.model_name or not self.record_id:
            return False

        if self.model_name not in self.env:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Model Not Found",
                    "message": "The related model is not available in this database.",
                    "type": "warning",
                    "sticky": False,
                },
            }

        record = self.env[self.model_name].sudo().browse(self.record_id)

        if not record.exists():
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Record Not Found",
                    "message": "The original record is no longer available.",
                    "type": "warning",
                    "sticky": False,
                },
            }

        return {
            "type": "ir.actions.act_window",
            "name": self.name or self.model_description or self.model_name,
            "res_model": self.model_name,
            "res_id": self.record_id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "current",
        }


class MstUserActivityLogLine(models.Model):
    _name = "mst.user.activity.log.line"
    _description = "User Activity Log Line"
    _order = "id asc"

    activity_log_id = fields.Many2one(
        "mst.user.activity.log",
        string="Activity Log",
        required=True,
        ondelete="cascade"
    )

    field_name = fields.Char(
        string="Field Name",
        readonly=True
    )

    field_label = fields.Char(
        string="Field Label",
        readonly=True
    )

    old_value = fields.Text(
        string="Old Value",
        readonly=True
    )

    new_value = fields.Text(
        string="New Value",
        readonly=True
    )

    is_view_field = fields.Boolean(
        string="View Change",
        readonly=True
    )


class BaseModelActivityAudit(models.AbstractModel):
    _inherit = "base"


    def _audit_create_activity_log_safely(self, values):
        try:
            with self.env.cr.savepoint():
                self.env["mst.user.activity.log"].sudo().with_context(
                    skip_mst_activity_audit=True
                ).create(values)
        except Exception as error:
            _logger.exception(
                "Activity audit log creation failed safely: %s",
                error
            )

        return True

    def _audit_skip_models(self):
        return {
            "mst.user.activity.log",
            "mst.user.activity.log.line",
            "mst.activity.log.model.config",
            "login.history",
            "login.failed.history",
            "ir.logging",
            "ir.config_parameter",
            "ir.attachment",
            "mail.message",
            "mail.mail",
            "mail.notification",
            "bus.bus",
            "bus.presence",
        }

    def _audit_is_enabled(self):
        return self.env["ir.config_parameter"].sudo().get_param(
            "mst_advanced_login_history.enable_activity_audit",
            "1"
        ) == "1"

    def _audit_should_skip(self):
        if self.env.context.get("skip_mst_activity_audit"):
            return True

        if not self._audit_is_enabled():
            return True

        if self._name in self._audit_skip_models():
            return True

        if getattr(self, "_transient", False):
            return True

        return False

    def _audit_related_parent_map(self):
        return {
            "sale.order.line": {
                "parent_field": "order_id",
                "parent_model": "sale.order",
                "amount_fields": [
                    "amount_untaxed",
                    "amount_tax",
                    "amount_total",
                ],
            },
            "purchase.order.line": {
                "parent_field": "order_id",
                "parent_model": "purchase.order",
                "amount_fields": [
                    "amount_untaxed",
                    "amount_tax",
                    "amount_total",
                ],
            },
            "account.move.line": {
                "parent_field": "move_id",
                "parent_model": "account.move",
                "amount_fields": [
                    "amount_untaxed",
                    "amount_tax",
                    "amount_total",
                    "amount_residual",
                ],
            },
        }

    def _audit_extra_watch_fields(self, record):
        possible_fields = [
            "amount_untaxed",
            "amount_tax",
            "amount_total",
            "amount_residual",
            "price_unit",
            "price_subtotal",
            "price_total",
            "product_uom_qty",
            "product_qty",
            "quantity",
            "discount",
        ]

        return [
            field_name
            for field_name in possible_fields
            if field_name in record._fields
        ]

    def _audit_get_request_details(self):
        values = {
            "session_id": "",
            "ip_address": "",
            "browser": "",
            "operating_system": "",
            "request_url": "",
            "request_method": "",
        }

        try:
            if not request:
                return values

            http_request = request.httprequest

            if http_request:
                user_agent_string = http_request.headers.get("User-Agent", "")

                if http_request.user_agent:
                    values["browser"] = (
                        http_request.user_agent.browser
                        or user_agent_string
                        or ""
                    )
                    values["operating_system"] = (
                        http_request.user_agent.platform
                        or ""
                    )

                ip_address = (
                    http_request.headers.get("X-Forwarded-For")
                    or http_request.headers.get("X-Real-IP")
                    or http_request.remote_addr
                    or ""
                )

                if ip_address and "," in ip_address:
                    ip_address = ip_address.split(",")[0].strip()

                values["ip_address"] = ip_address
                values["request_url"] = http_request.path or ""
                values["request_method"] = http_request.method or ""

            if request.session:
                values["session_id"] = request.session.sid or ""

        except Exception:
            pass

        return values

    def _audit_get_model_description(self, model_name):
        try:
            ir_model = self.env["ir.model"].sudo()._get(model_name)
            return ir_model.name or model_name
        except Exception:
            return model_name

    def _audit_get_module_name(self, model_name):
        module_name = ""

        try:
            ir_model = self.env["ir.model"].sudo()._get(model_name)

            data_record = self.env["ir.model.data"].sudo().search(
                [
                    ("model", "=", "ir.model"),
                    ("res_id", "=", ir_model.id),
                ],
                limit=1
            )

            if data_record:
                module_name = data_record.module

        except Exception:
            module_name = ""

        return module_name

    def _audit_get_related_parent_model(self, model_name):
        related_map = self._audit_related_parent_map()
        related_data = related_map.get(model_name)

        if related_data:
            return related_data.get("parent_model")

        return False

    def _audit_get_model_config(self, model_name, action_type):
        try:
            Config = self.env["mst.activity.log.model.config"].sudo()

            table_name = Config._table

            with self.env.cr.savepoint():
                self.env.cr.execute(
                    "SELECT to_regclass(%s)",
                    ("public.%s" % table_name,)
                )
                table_exists = self.env.cr.fetchone()[0]

            if not table_exists:
                return False

            configs = Config.search([
                ("active", "=", True),
            ])

            parent_model_name = self._audit_get_related_parent_model(model_name)

            for config in configs:
                configured_model_names = config.model_ids.mapped("model")

                matched = model_name in configured_model_names

                if (
                    not matched
                    and config.include_related_line_models
                    and parent_model_name
                    and parent_model_name in configured_model_names
                ):
                    matched = True

                if not matched:
                    continue

                if action_type == "create" and not config.track_create:
                    continue

                if action_type == "modify" and not config.track_modify:
                    continue

                if action_type == "delete" and not config.track_delete:
                    continue

                return config

        except Exception as error:
            _logger.exception(
                "Model log configuration check failed safely: %s",
                error
            )

        return False

    def _audit_get_record_name(self, record):
        try:
            return record.display_name or "%s,%s" % (record._name, record.id)
        except Exception:
            return "%s,%s" % (record._name, record.id)

    def _audit_format_value(self, value):
        if value is False or value is None:
            return ""

        if isinstance(value, models.BaseModel):
            if not value:
                return ""

            if len(value) == 1:
                return "%s [%s]" % (
                    value.display_name,
                    value.id
                )

            names = []

            for rec in value[:20]:
                names.append("%s [%s]" % (rec.display_name, rec.id))

            if len(value) > 20:
                names.append("...")

            return ", ".join(names)

        if isinstance(value, (list, tuple, dict)):
            try:
                return json.dumps(
                    value,
                    ensure_ascii=False,
                    default=str,
                    indent=2
                )
            except Exception:
                return str(value)

        return str(value)

    def _audit_get_field_value(self, record, field_name):
        if field_name not in record._fields:
            return ""

        field = record._fields[field_name]

        if field.type == "binary":
            return "[Binary Data]"

        try:
            value = record[field_name]
            return self._audit_format_value(value)
        except Exception:
            return ""

    def _audit_get_field_label(self, record, field_name):
        if field_name in record._fields:
            return record._fields[field_name].string or field_name

        return field_name

    def _audit_get_watch_field_names(self, record, vals):
        field_names = set(vals.keys())

        for field_name in self._audit_extra_watch_fields(record):
            field_names.add(field_name)

        valid_fields = []

        for field_name in field_names:
            if field_name not in record._fields:
                continue

            field = record._fields[field_name]

            if field.type == "binary":
                continue

            valid_fields.append(field_name)

        return valid_fields

    def _audit_prepare_changes_before_write(self, vals):
        old_values = {}

        for record in self:
            old_values[record.id] = {}

            field_names = self._audit_get_watch_field_names(record, vals)

            for field_name in field_names:
                old_values[record.id][field_name] = {
                    "label": self._audit_get_field_label(record, field_name),
                    "value": self._audit_get_field_value(record, field_name),
                }

        return old_values

    def _audit_prepare_changes_after_write(self, vals):
        new_values = {}

        for record in self:
            new_values[record.id] = {}

            field_names = self._audit_get_watch_field_names(record, vals)

            for field_name in field_names:
                new_values[record.id][field_name] = {
                    "label": self._audit_get_field_label(record, field_name),
                    "value": self._audit_get_field_value(record, field_name),
                }

        return new_values

    def _audit_prepare_create_changes(self, record, vals):
        line_commands = []

        field_names = self._audit_get_watch_field_names(record, vals)

        for field_name in field_names:
            new_value = self._audit_get_field_value(record, field_name)

            if not new_value:
                continue

            line_commands.append(
                (
                    0,
                    0,
                    {
                        "field_name": field_name,
                        "field_label": self._audit_get_field_label(record, field_name),
                        "old_value": "",
                        "new_value": new_value,
                        "is_view_field": field_name in [
                            "arch",
                            "arch_db",
                            "arch_base",
                        ],
                    },
                )
            )

        return line_commands

    def _audit_prepare_delete_changes(self, record):
        line_commands = []

        for field_name, field in record._fields.items():
            if field.type in ["binary", "one2many", "many2many"]:
                continue

            try:
                old_value = self._audit_get_field_value(record, field_name)
            except Exception:
                old_value = ""

            if not old_value:
                continue

            line_commands.append(
                (
                    0,
                    0,
                    {
                        "field_name": field_name,
                        "field_label": field.string or field_name,
                        "old_value": old_value,
                        "new_value": "",
                        "is_view_field": field_name in [
                            "arch",
                            "arch_db",
                            "arch_base",
                        ],
                    },
                )
            )

        return line_commands

    def _audit_prepare_line_commands_from_old_new_values(
        self,
        old_values,
        new_values,
        vals
    ):
        line_commands = []

        field_names = set(vals.keys())

        for record_id, values in old_values.items():
            for field_name in values.keys():
                field_names.add(field_name)

        for record_id, values in new_values.items():
            for field_name in values.keys():
                field_names.add(field_name)

        for field_name in field_names:
            old_data = {}
            new_data = {}

            for values in old_values.values():
                if field_name in values:
                    old_data = values.get(field_name, {})
                    break

            for values in new_values.values():
                if field_name in values:
                    new_data = values.get(field_name, {})
                    break

            old_value = old_data.get("value", "")
            new_value = new_data.get("value", "")

            if old_value == new_value:
                continue

            line_commands.append(
                (
                    0,
                    0,
                    {
                        "field_name": field_name,
                        "field_label": (
                            new_data.get("label")
                            or old_data.get("label")
                            or field_name
                        ),
                        "old_value": old_value,
                        "new_value": new_value,
                        "is_view_field": field_name in [
                            "arch",
                            "arch_db",
                            "arch_base",
                        ],
                    },
                )
            )

        return line_commands

    def _audit_create_log(self, record, action_type, line_commands):
        try:
            if action_type == "modify" and not line_commands:
                return True

            request_details = self._audit_get_request_details()

            has_view_changes = False

            for command in line_commands:
                if command[2].get("is_view_field"):
                    has_view_changes = True
                    break

            model_config = self._audit_get_model_config(
                record._name,
                action_type
            )

            self.env["mst.user.activity.log"].sudo().with_context(
                skip_mst_activity_audit=True
            ).create({
                    "name": self._audit_get_record_name(record),
                    "user_id": self.env.user.id,
                    "login": self.env.user.login,
                    "model_name": record._name,
                    "model_description": self._audit_get_model_description(record._name),
                    "module_name": self._audit_get_module_name(record._name),
                    "model_config_id": model_config.id if model_config else False,
                    "model_log_enabled": True if model_config else False,
                    "record_id": record.id,
                    "action_type": action_type,
                    "performed_date": fields.Datetime.now(),
                    "session_id": request_details.get("session_id"),
                    "ip_address": request_details.get("ip_address"),
                    "browser": request_details.get("browser"),
                    "operating_system": request_details.get("operating_system"),
                    "request_url": request_details.get("request_url"),
                    "request_method": request_details.get("request_method"),
                    "has_changes": bool(line_commands),
                    "has_view_changes": has_view_changes,
                    "line_ids": line_commands,
                }
            )

        except Exception as error:
            _logger.exception("Activity audit log creation failed: %s", error)

        return True

    def _audit_get_parent_records_before_change(self):
        parent_data = {}
        related_map = self._audit_related_parent_map()
        related_info = related_map.get(self._name)

        if not related_info:
            return parent_data

        parent_field = related_info.get("parent_field")
        amount_fields = related_info.get("amount_fields", [])

        for record in self:
            parent = record[parent_field]

            if not parent:
                continue

            parent_data[parent.id] = {
                "record": parent,
                "values": {},
            }

            for field_name in amount_fields:
                if field_name in parent._fields:
                    parent_data[parent.id]["values"][field_name] = {
                        "label": self._audit_get_field_label(parent, field_name),
                        "value": self._audit_get_field_value(parent, field_name),
                    }

        return parent_data

    def _audit_create_parent_amount_change_logs(self, parent_data):
        for data in parent_data.values():
            parent = data.get("record")

            if not parent or not parent.exists():
                continue

            old_values = data.get("values", {})
            line_commands = []

            for field_name, old_data in old_values.items():
                new_value = self._audit_get_field_value(parent, field_name)
                old_value = old_data.get("value", "")

                if old_value == new_value:
                    continue

                line_commands.append(
                    (
                        0,
                        0,
                        {
                            "field_name": field_name,
                            "field_label": old_data.get("label") or field_name,
                            "old_value": old_value,
                            "new_value": new_value,
                            "is_view_field": False,
                        },
                    )
                )

            if line_commands:
                self._audit_create_log(
                    record=parent,
                    action_type="modify",
                    line_commands=line_commands
                )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        if self._audit_should_skip():
            return records

        for record, vals in zip(records, vals_list):
            line_commands = record._audit_prepare_create_changes(record, vals)

            record._audit_create_log(
                record=record,
                action_type="create",
                line_commands=line_commands
            )

        return records

    def write(self, vals):
        if self._audit_should_skip():
            return super().write(vals)

        old_values = self._audit_prepare_changes_before_write(vals)
        parent_data = self._audit_get_parent_records_before_change()

        result = super().write(vals)

        new_values = self._audit_prepare_changes_after_write(vals)

        for record in self:
            record_old_values = {
                record.id: old_values.get(record.id, {})
            }

            record_new_values = {
                record.id: new_values.get(record.id, {})
            }

            line_commands = self._audit_prepare_line_commands_from_old_new_values(
                record_old_values,
                record_new_values,
                vals
            )

            record._audit_create_log(
                record=record,
                action_type="modify",
                line_commands=line_commands
            )

        self._audit_create_parent_amount_change_logs(parent_data)

        return result

    def unlink(self):
        if self._audit_should_skip():
            return super().unlink()

        parent_data = self._audit_get_parent_records_before_change()
        audit_data = []

        for record in self:
            audit_data.append(
                {
                    "record_id": record.id,
                    "record_name": self._audit_get_record_name(record),
                    "model_name": record._name,
                    "line_commands": self._audit_prepare_delete_changes(record),
                }
            )

        result = super().unlink()

        for data in audit_data:
            try:
                request_details = self._audit_get_request_details()

                model_name = data.get("model_name")

                model_config = self._audit_get_model_config(
                    model_name,
                    "delete"
                )

                self.env["mst.user.activity.log"].sudo().with_context(
                    skip_mst_activity_audit=True
                ).create(
                    {
                        "name": data.get("record_name"),
                        "user_id": self.env.user.id,
                        "login": self.env.user.login,
                        "model_name": model_name,
                        "model_description": self._audit_get_model_description(model_name),
                        "module_name": self._audit_get_module_name(model_name),
                        "model_config_id": model_config.id if model_config else False,
                        "model_log_enabled": True if model_config else False,
                        "record_id": data.get("record_id"),
                        "action_type": "delete",
                        "performed_date": fields.Datetime.now(),
                        "session_id": request_details.get("session_id"),
                        "ip_address": request_details.get("ip_address"),
                        "browser": request_details.get("browser"),
                        "operating_system": request_details.get("operating_system"),
                        "request_url": request_details.get("request_url"),
                        "request_method": request_details.get("request_method"),
                        "has_changes": bool(data.get("line_commands")),
                        "has_view_changes": False,
                        "line_ids": data.get("line_commands"),
                    }
                )

            except Exception as error:
                _logger.exception("Delete audit log creation failed: %s", error)

        self._audit_create_parent_amount_change_logs(parent_data)

        return result