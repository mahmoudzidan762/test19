# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from odoo import api, fields, models


class PurchaseOrder(models.Model):

    _inherit = "purchase.order"

    requisition_order = fields.Char(string="Requisition Order")
