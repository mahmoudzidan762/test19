# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from odoo import api, fields, models


class hr_department(models.Model):
    _inherit = "hr.department"

    destination_location_id = fields.Many2one(
        "stock.location", string="Destination Location"
    )
