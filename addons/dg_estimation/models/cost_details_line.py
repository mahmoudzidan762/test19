from odoo import models, fields, api, _
from odoo.exceptions import UserError


class CostDetailsLine(models.Model):
    _name = 'cost.details.line'

    material_cost_details_id = fields.Many2one('cost.details', string='Material Cost Details')
    tools_cost_details_id = fields.Many2one('cost.details', string='Tools Cost Details')
    labor_cost_details_id = fields.Many2one('cost.details', string='Labor Cost Details')
    delivery_cost_details_id = fields.Many2one('cost.details', string='Delivery Cost Details')
    product_id = fields.Many2one('product.template', string='Items')
    uom_id = fields.Many2one('uom.uom', string='UOM', related='product_id.uom_id')
    cost_price = fields.Float(string='Cost', default=0.0)
    total_cost = fields.Float(string='Total', compute='_compute_total_cost')
    qty = fields.Float(string='Master QTY', default=0.0)
    new_qty = fields.Float(string='New Qty')
    prev_pur = fields.Float(string='Previous Purchase')
    curr_pur = fields.Float(string='Current Purchase')
    unit_est_price = fields.Float(string='Unit Estimate Price')
    unit_pur_price = fields.Float(string='Unit Purchase Price')
    scrap = fields.Float(string='Scrap %', default=0.0)
    cost_center_id = fields.Many2one('account.analytic.account', string='Cost Center')

    @api.depends('qty', 'cost_price', 'scrap')
    def _compute_total_cost(self):
        for record in self:
            record.total_cost = record.qty * record.cost_price
            if record.scrap:
                record.total_cost += record.scrap * record.cost_price
