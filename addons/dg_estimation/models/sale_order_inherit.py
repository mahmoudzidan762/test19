from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SaleOrderInherit(models.Model):
    _inherit = 'sale.order'

    estimation_id = fields.Many2one('estimation', string='Estimation')

    def action_confirm(self):
        res = super().action_confirm()
        est = self.env['estimation'].search([('sale_order_id', '=', self.id)])
        est.write({'state': 'contract'})
        self.env['bid.file'].search([('lead_id', '=', est.lead_id.id)]).write({'state': 'project'})
        return res
