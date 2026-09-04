# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    requisition_order = fields.Char(string="Requisition Order")
