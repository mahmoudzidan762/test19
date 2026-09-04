from odoo import models, fields, api, _
from odoo.exceptions import UserError


class BOQSubItem(models.Model):
    _name = 'boq.sub.item'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Bill Of Quantity Sub Item'

    boq_line_id = fields.Many2one('bill.of.quantity.line', string='Bill Of Quantity Line', readonly=True)
    boq_id = fields.Many2one('bill.of.quantity', string='Bill Of Quantity', readonly=True, related='boq_line_id.boq_id')
    sequence = fields.Char(string='Sequence', readonly=True, store=True, related='boq_line_id.sequence')
    item = fields.Char(string='Item', related='boq_line_id.items', store=True)
    billed_progress = fields.Float(string='Billed Progress %', related='boq_line_id.billed_progress', store=True)
    onsite_progress = fields.Float(string='Onsite Progress %', related='boq_line_id.onsite_progress', store=True)
    master_qty = fields.Float(string='Master Qty', related='boq_line_id.qty', store=True)
    new_qty = fields.Float(string='New Qty', related='boq_line_id.new_variation_qty', store=True)
    unit_price = fields.Float(string='Unit Price', related='boq_line_id.unit_price', store=True)
    total_price = fields.Float(string='Total Price', compute='_compute_total_price', store=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('awaiting_approval', 'Awaiting Approval'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', readonly=True, default='draft', tracking=True)
    material_cost_ids = fields.One2many('cost.details.line', 'material_sub_items_details_id',
                                        string='Material Sub Items Details')
    tools_cost_ids = fields.One2many('cost.details.line', 'tools_sub_items_details_id',
                                     string='Tools Sub Items Details')
    labor_cost_ids = fields.One2many('cost.details.line', 'labor_sub_items_details_id',
                                     string='Labor Sub Items Details')
    delivery_cost_ids = fields.One2many('cost.details.line', 'delivery_sub_items_details_id',
                                        string='Delivery Sub Items Details')
    lead_id = fields.Many2one('crm.lead', string='Project', related='boq_id.lead_id', store=True)
    material_requisition_count = fields.Integer(string='Material Requisitions',
                                                compute='_compute_material_requisition_count')

    def _compute_material_requisition_count(self):
        for rec in self:
            rec.material_requisition_count = self.env['material.purchase.requisition'].search_count(
                [('boq_sub_item_id', '=', rec.id)])

    def action_open_material_requisitions(self):
        for rec in self:
            return {
                'name': _('Material Requisitions'),
                'type': 'ir.actions.act_window',
                'res_model': 'material.purchase.requisition',
                'view_mode': 'list,form',
                'domain': [('boq_sub_item_id', '=', rec.id), ('sequence', '=', rec.sequence), ('item', '=', rec.item)],
                'target': 'current',
            }

    def action_create_material_requisitions(self):
        for rec in self:
            vals = []
            for line in rec.material_cost_ids:
                vals.append((0, 0, {
                    'request_action': 'purchase order',
                    'product_id': line.product_id.id,
                    'quantity': line.new_qty,
                    'unit_of_measure': line.uom_id.id,
                    'cost_center_id': line.cost_center_id.id,
                }))
            for line in rec.tools_cost_ids:
                vals.append((0, 0, {
                    'request_action': 'purchase order',
                    'product_id': line.product_id.id,
                    'quantity': line.new_qty,
                    'unit_of_measure': line.uom_id.id,
                    'cost_center_id': line.cost_center_id.id,
                }))
            return {
                'name': _('Material Requisition'),
                'type': 'ir.actions.act_window',
                'res_model': 'material.purchase.requisition',
                'view_mode': 'form',
                'target': 'current',
                'context': {
                    'default_boq_sub_item_id': rec.id,
                    'default_employee_id': self.env.user.employee_id.id,
                    'default_requisition_lines': vals,
                    'default_lead_id': rec.boq_id.lead_id.id or False,
                }
            }

    @api.depends('new_qty', 'unit_price')
    def _compute_total_price(self):
        for rec in self:
            rec.total_price = rec.new_qty * rec.unit_price

    def action_submit(self):
        pass

    def action_cancel(self):
        pass
