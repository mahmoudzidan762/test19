from odoo import models, fields, api, _


class PurchaseRequisitionInherit(models.Model):
    _inherit = 'purchase.requisition'

    lead_id = fields.Many2one('crm.lead', string='Project')
    residual_is_zero = fields.Boolean(string='Residual is Zero', compute='_compute_residual_is_zero', default=False)

    @api.depends('line_ids.residual_qty')
    def _compute_residual_is_zero(self):
        for requisition in self:
            requisition.residual_is_zero = all(line.residual_qty == 0 for line in requisition.line_ids) or False


class PurchaseRequisitionLineInherit(models.Model):
    _inherit = 'purchase.requisition.line'

    residual_qty = fields.Integer(string='Residual', compute='_compute_residual_qty', store=True)
    total_price = fields.Float(string='Total', compute='_compute_total_price', store=True)

    @api.depends('product_qty', 'price_unit')
    def _compute_total_price(self):
        for line in self:
            line.total_price = line.product_qty * line.price_unit

    @api.depends('product_qty', 'qty_ordered')
    def _compute_residual_qty(self):
        for line in self:
            line.residual_qty = line.product_qty - line.qty_ordered
