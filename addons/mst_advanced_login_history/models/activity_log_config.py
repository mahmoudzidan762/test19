# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class MstActivityLogModelConfig(models.Model):
    _name = "mst.activity.log.model.config"
    _description = "Activity Log Model Configuration"
    _rec_name = "name"
    _order = "sequence, id"

    sequence = fields.Integer(
        string="Sequence",
        default=10
    )

    name = fields.Char(
        string="Configuration Name",
        compute="_compute_name",
        store=True
    )

    active = fields.Boolean(
        string="Active",
        default=True
    )

    model_ids = fields.Many2many(
        "ir.model",
        "mst_activity_log_config_ir_model_rel",
        "config_id",
        "model_id",
        string="Models",
        required=True,
        domain=[
            ("transient", "=", False)
        ]
    )

    model_names = fields.Char(
        string="Model Names",
        compute="_compute_model_details",
        store=True
    )

    technical_model_names = fields.Char(
        string="Technical Models",
        compute="_compute_model_details",
        store=True
    )

    module_names = fields.Char(
        string="Modules",
        compute="_compute_model_details",
        store=True
    )

    model_count = fields.Integer(
        string="Model Count",
        compute="_compute_model_details",
        store=True
    )

    track_create = fields.Boolean(
        string="Track Create",
        default=True
    )

    track_modify = fields.Boolean(
        string="Track Modify",
        default=True
    )

    track_delete = fields.Boolean(
        string="Track Delete",
        default=True
    )

    include_related_line_models = fields.Boolean(
        string="Include Related Line Models",
        default=True,
        help="If enabled, selecting Sale Order will also include Sale Order Lines, "
             "Purchase Order will include Purchase Order Lines, and Invoice will include Journal Items."
    )

    notes = fields.Text(
        string="Notes"
    )

    @api.depends("model_ids")
    def _compute_name(self):
        for record in self:
            if record.model_ids:
                model_names = record.model_ids.mapped("name")
                record.name = " / ".join(model_names[:4])

                if len(model_names) > 4:
                    record.name += " ..."
            else:
                record.name = "Model Log Configuration"

    @api.depends("model_ids")
    def _compute_model_details(self):
        IrModelData = self.env["ir.model.data"].sudo()

        for record in self:
            record.model_count = len(record.model_ids)
            record.model_names = ", ".join(record.model_ids.mapped("name"))
            record.technical_model_names = ", ".join(record.model_ids.mapped("model"))

            module_list = []

            for model in record.model_ids:
                data_record = IrModelData.search(
                    [
                        ("model", "=", "ir.model"),
                        ("res_id", "=", model.id),
                    ],
                    limit=1
                )

                if data_record and data_record.module:
                    module_list.append(data_record.module)

            record.module_names = ", ".join(sorted(set(module_list)))

    @api.constrains("model_ids", "active")
    def _check_duplicate_active_models(self):
        for record in self:
            if not record.active or not record.model_ids:
                continue

            other_configs = self.search(
                [
                    ("id", "!=", record.id),
                    ("active", "=", True),
                ]
            )

            selected_model_ids = set(record.model_ids.ids)

            for config in other_configs:
                duplicate_ids = selected_model_ids.intersection(
                    set(config.model_ids.ids)
                )

                if duplicate_ids:
                    duplicate_models = self.env["ir.model"].browse(
                        list(duplicate_ids)
                    ).mapped("name")

                    raise ValidationError(
                        "These models are already configured in another active configuration: %s"
                        % ", ".join(duplicate_models)
                    )

    def action_view_model_logs(self):
        self.ensure_one()

        model_names = self.model_ids.mapped("model")

        if self.include_related_line_models:
            model_names += self._get_related_line_model_names(model_names)

        return {
            "type": "ir.actions.act_window",
            "name": "%s Logs" % (self.name or "Model"),
            "res_model": "mst.user.activity.log",
            "view_mode": "list,form",
            "domain": [
                ("model_log_enabled", "=", True),
                ("model_name", "in", list(set(model_names))),
            ],
            "context": {
                "search_default_group_model": 1,
            },
            "target": "current",
        }

    def _get_related_line_model_names(self, model_names):
        related_map = {
            "sale.order": ["sale.order.line"],
            "purchase.order": ["purchase.order.line"],
            "account.move": ["account.move.line"],
            "stock.picking": ["stock.move", "stock.move.line"],
        }

        related_models = []

        for model_name in model_names:
            related_models += related_map.get(model_name, [])

        return related_models