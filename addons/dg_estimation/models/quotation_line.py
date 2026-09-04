from odoo import models, fields, api, _
from odoo.exceptions import UserError


class QuotationLine(models.Model):
    _name = 'quotation.line'
    _description = 'Quotation Line'

    estimation_id = fields.Many2one('estimation', string='Estimation')
    items = fields.Char(string='Items')
    uom_id = fields.Many2one('uom.uom', string='UOM', store=True)
    qty = fields.Float(string='QTY', default=1.0)
    tax_ids = fields.Many2one('account.tax', string='Tax')
    unit_price = fields.Float(string='Unit Price', default=0.0)
    total_unit_price = fields.Float(string='Total Unit Price', default=0.0)
    total_price = fields.Float(string='Total Price', default=0.0)
