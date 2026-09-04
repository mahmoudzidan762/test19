# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from odoo import api, fields, models


class hr_employee(models.Model):
    _inherit = "hr.employee"

    destination_loc_id = fields.Many2one(
        "stock.location", string="Destination Location"
    )
