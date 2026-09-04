from odoo import models, fields, api, _
from odoo.exceptions import UserError


class DirectCostLine(models.Model):
    _name = 'direct.cost.line'
    _description = 'Direct Cost Line'

    sequence = fields.Char(string='Sequence')
    estimation_id = fields.Many2one('estimation', string='Estimation')
    items = fields.Char(string='Items')
    description = fields.Text(string='Description')
    uom_id = fields.Many2one('uom.uom', string='UOM', store=True)
    type_of_implement = fields.Selection([
        ('inhouse', 'In House'),
        ('subcontractor', 'Subcontractor'),
        ('running', 'Running'),
    ], string='Type of Implement', default='inhouse')
    material = fields.Float(string='Material')
    labor = fields.Float(string='Labor')
    tools = fields.Float(string='Tools')
    delivery = fields.Float(string='Delivery')
    qty = fields.Float(string='QTY', default=1.0)
    notes = fields.Html(string='Notes')
    cost_details_id = fields.Many2one('cost.details', store=True)
    margin = fields.Float(string='Margin %', default=0.0)
    overhead = fields.Float(string='Overhead %', default=0.0)
    tax_ids = fields.Many2one('account.tax', string='Tax')
    # TOTALS
    cost_unit = fields.Float(string='Unit Estimate', default=0.0, compute='_compute_totals',
                             inverse="_inverse_unit_estimate", store=True)
    total_cost_unit = fields.Float(string='Unit Selling', default=0.0, compute='_compute_totals')
    total_no_tax = fields.Float(string='TSU', default=0.0, compute='_compute_totals')
    final_total = fields.Float(string='TAT', default=0.0, compute='_compute_totals')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        for estimation in records.mapped('estimation_id'):
            seq = 1

            lines = estimation.direct_cost_line_ids.sorted('id')

            for line in lines:
                line.sequence = f'DC/{seq:05d}'
                seq += 1

        return records

    def _inverse_unit_estimate(self):
        for rec in self:
            if rec.type_of_implement == 'subcontractor':
                rec.cost_unit = rec.cost_unit

    def action_create_cost_details(self):
        self.ensure_one()
        if self.cost_details_id:
            return {
                'name': _('Cost Details'),
                'type': 'ir.actions.act_window',
                'res_model': 'cost.details',
                'view_mode': 'form',
                'res_id': self.cost_details_id.id
            }
        else:
            res = self.env['cost.details'].create({
                'direct_cost_line_id': self.id,
                'items': self.items,
                'lead_id': self.estimation_id.lead_id.id
            })
            self.cost_details_id = res.id
            return {
                'name': _('Cost Details'),
                'type': 'ir.actions.act_window',
                'res_model': 'cost.details',
                'view_mode': 'form',
                'res_id': res.id
            }

    @api.depends('material', 'labor', 'tools', 'delivery', 'cost_unit', 'overhead', 'total_cost_unit', 'margin', 'qty',
                 'total_no_tax', 'tax_ids')
    def _compute_totals(self):
        for line in self:
            if line.type_of_implement == 'inhouse':
                line.cost_unit = line.material + line.labor + line.tools + line.delivery
            else:
                line.cost_unit = line.cost_unit
            line.total_cost_unit = line.cost_unit + (line.cost_unit * (line.overhead / 100))
            line.total_cost_unit += line.total_cost_unit * (line.margin / 100)
            line.total_no_tax = line.total_cost_unit * line.qty
            line.final_total = line.total_no_tax + (line.total_no_tax * (line.tax_ids.amount / 100))

    def unlink(self):
        for rec in self:
            if rec.cost_details_id:
                rec.cost_details_id.unlink()
        return super().unlink()
