from odoo import models, fields, api, _
from odoo.exceptions import UserError


class InDirectCostSummaryLine(models.Model):
    _name = 'indirect.cost.summary.line'
    _description = 'In-Direct Cost Summary Line'

    estimation_id = fields.Many2one('estimation', string='Estimation')
    category_id = fields.Many2one('product.category', string='Category')
    total_per_category = fields.Float(string='Total Indirect Es', compute="compute_totals", store=True)
    total_per_category_to_total_indirect = fields.Float(string='% from Indirect Estimation', compute="compute_totals",
                                                        store=True)
    total_per_category_to_total_direct = fields.Float(string='% from Direct Estimation', compute="compute_totals",
                                                      store=True)

    @api.depends('category_id', 'estimation_id.total_indirect_estimation',
                 'estimation_id.total_direct_estimation')
    def compute_totals(self):
        for rec in self:
            s = 0
            for line in rec.estimation_id.indirect_cost_line_ids:
                if line.category_id == rec.category_id:
                    s += line.total
            rec.total_per_category = s
            if rec.estimation_id.total_indirect_estimation:
                rec.total_per_category_to_total_indirect = (s / rec.estimation_id.total_indirect_estimation) * 100
            if rec.estimation_id.total_direct_estimation:
                rec.total_per_category_to_total_direct = (s / rec.estimation_id.total_direct_estimation) * 100
