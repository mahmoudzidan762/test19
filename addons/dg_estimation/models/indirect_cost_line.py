from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

logger = logging.getLogger(__name__)


class InDirectCostLine(models.Model):
    _name = 'indirect.cost.line'
    _description = 'In-Direct Cost Line'

    estimation_id = fields.Many2one('estimation', string='Estimation')
    category_id = fields.Many2one('product.category', string='Category')
    product_id = fields.Many2one('product.template', string='Item')
    product_domain = fields.Char(string='Product Domain', compute='_compute_product_domain')
    duration = fields.Float(string='Duration (months)', default=1.0)
    qty = fields.Float(string='QTY', default=1.0)
    cost_price = fields.Float(string='Cost SAR', default=0.0)
    total = fields.Float(string='Total Indirect Estimation SAR', compute='_compute_totals', store=True)
    display_type = fields.Selection([
        ('line', 'Line'),
        ('section', 'Section'),
        ('note', 'Note'),
    ], default='line')

    @api.onchange('category_id')
    def _compute_product_domain(self):
        for line in self:
            if line.category_id:
                line.product_domain = "[('categ_id', '=', %s)]" % line.category_id.id
            else:
                products = self.env['product.template'].search([])
                line.product_domain = [('id', 'in', products.ids)]

    @api.depends('qty', 'cost_price', 'duration')
    def _compute_totals(self):
        for line in self:
            line.total = line.qty * line.cost_price * line.duration
