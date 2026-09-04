from odoo import models, fields, api


class CostDetails(models.Model):
    _name = 'cost.details'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Cost Details'

    sequence = fields.Char(string='Sequence', related='direct_cost_line_id.sequence')
    items = fields.Char(string='Item', related='direct_cost_line_id.items')
    direct_cost_line_id = fields.Many2one('direct.cost.line', string='Direct Cost Line')
    lead_id = fields.Many2one('crm.lead', string='Project Name', related='direct_cost_line_id.estimation_id.lead_id')
    material_cost_ids = fields.One2many('cost.details.line', 'material_cost_details_id', string='Material Cost Details')
    tools_cost_ids = fields.One2many('cost.details.line', 'tools_cost_details_id', string='Tools Cost Details')
    labor_cost_ids = fields.One2many('cost.details.line', 'labor_cost_details_id', string='Labor Cost Details')
    delivery_cost_ids = fields.One2many('cost.details.line', 'delivery_cost_details_id', string='Delivery Cost Details')
    material_subtotal = fields.Float(string='Subtotal', compute='_compute_material_subtotal', store=True)
    tools_subtotal = fields.Float(string='Subtotal', compute='_compute_tools_subtotal', store=True)
    labor_subtotal = fields.Float(string='Subtotal', compute='_compute_labor_subtotal', store=True)
    delivery_subtotal = fields.Float(string='Subtotal', compute='_compute_delivery_subtotal', store=True)
    notes = fields.Html(string='Notes')
    created_by = fields.Many2one(
        'res.users',
        string='Created By',
        default=lambda self: self.env.user,
        readonly=True
    )
    date = fields.Date(string='Date', default=fields.Date.context_today)

    @api.depends('material_cost_ids.total_cost')
    def _compute_material_subtotal(self):
        for record in self:
            record.material_subtotal = sum(line.total_cost for line in record.material_cost_ids)
            record.direct_cost_line_id.material = record.material_subtotal

    @api.depends('tools_cost_ids.total_cost')
    def _compute_tools_subtotal(self):
        for record in self:
            record.tools_subtotal = sum(line.total_cost for line in record.tools_cost_ids)
            record.direct_cost_line_id.tools = record.tools_subtotal

    @api.depends('labor_cost_ids.total_cost')
    def _compute_labor_subtotal(self):
        for record in self:
            record.labor_subtotal = sum(line.total_cost for line in record.labor_cost_ids)
            record.direct_cost_line_id.labor = record.labor_subtotal

    @api.depends('delivery_cost_ids.total_cost')
    def _compute_delivery_subtotal(self):
        for record in self:
            record.delivery_subtotal = sum(line.total_cost for line in record.delivery_cost_ids)
            record.direct_cost_line_id.delivery = record.delivery_subtotal
