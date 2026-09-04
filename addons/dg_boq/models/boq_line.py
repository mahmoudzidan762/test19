from odoo import models, fields, api, _
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta


class BillOfQuantityLine(models.Model):
    _name = 'bill.of.quantity.line'
    _description = 'Bill Of Quantity Line'

    name = fields.Char(string='Description')
    boq_id = fields.Many2one('bill.of.quantity', string='Bill Of Quantity')
    lead_id = fields.Many2one('crm.lead', string='Project', related='boq_id.lead_id', store=True)
    partner_id = fields.Many2one('res.partner', string='Customer', related='boq_id.partner_id', store=True)
    variation_id = fields.Many2one('variation.order', string='Variation Order')
    ipc_id = fields.Many2one('ipc.certificate', string='Payment Certificate')
    sequence = fields.Char(string='Sequence')
    items = fields.Char(string='Items')
    uom_id = fields.Many2one('uom.uom', string='UOM', store=True)
    qty = fields.Float(string='Master QTY', default=0.0)
    new_variation_qty = fields.Float(string='New QTY')
    surplus_qty = fields.Float(string='Surplus QTY', default=0.0, compute='_compute_surplus_and_deficit',
                               store=True)
    deficit_qty = fields.Float(string='Deficit QTY', default=0.0, compute='_compute_surplus_and_deficit',
                               store=True)
    surplus_value = fields.Float(string='Surplus Value', default=0.0, compute='_compute_surplus_and_deficit',
                                 store=True)
    deficit_value = fields.Float(string='Deficit Value', default=0.0, compute='_compute_surplus_and_deficit',
                                 store=True)
    total_previous = fields.Float(string='Total Previous')
    total_current = fields.Float(string='Total Current')
    total_cumulative = fields.Float(string='Total Accumulative', compute='_compute_total_cumulative', store=True)
    billed_progress = fields.Float(string='Billing Progress %', compute='_compute_billed_progress', store=True)
    onsite_progress = fields.Float(string='Onsite Progress %', compute='_compute_onsite_progress', store=True)
    onsite_amount = fields.Float(string='Onsite Amount')
    type_of_implement = fields.Selection([
        ('inhouse', 'In House'),
        ('subcontractor', 'Subcontractor'),
        ('running', 'Running'),
    ], string='Type of Implement', default='inhouse')
    margin = fields.Float(string='Margin %', default=0.0)
    overhead = fields.Float(string='Overhead %', default=0.0)
    boq_sub_item_id = fields.Many2one('boq.sub.item', string='Bill Of Quantity Sub Item')
    unit_price = fields.Float(string='Unit Price', default=1.0)
    remaining = fields.Float(string='Remaining', compute='_compute_remaining', store=True)
    total_contract_value = fields.Float(string='Total Contract Value', default=0.0)
    total_estimated_value = fields.Float(string='Total Estimated Value', default=0.0)
    notes = fields.Text(string='Notes')
    origin_line_id = fields.Many2one('bill.of.quantity.line')
    from_button = fields.Boolean(string='From Button', default=False, compute="_compute_from_button")
    source_line_id = fields.Many2one('bill.of.quantity.line')
    ipc_total = fields.Float(string='Total', compute='_compute_ipc_total', store=True)

    @api.depends('new_variation_qty', 'total_previous')
    def _compute_billed_progress(self):
        for rec in self:
            if rec.total_previous and rec.new_variation_qty:
                rec.billed_progress = rec.total_previous / rec.new_variation_qty

    @api.depends('onsite_amount', 'new_variation_qty')
    def _compute_onsite_progress(self):
        for rec in self:
            if rec.onsite_amount and rec.new_variation_qty:
                rec.onsite_progress = rec.onsite_amount / rec.new_variation_qty

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        for boq in records.mapped('boq_id'):
            seq = 1

            lines = boq.boq_line_ids.sorted('id')

            for line in lines:
                line.sequence = f'BOQL/{seq:05d}'
                seq += 1

        return records

    @api.depends('unit_price', 'total_current')
    def _compute_ipc_total(self):
        for rec in self:
            rec.ipc_total = rec.unit_price * rec.total_current

    @api.depends('new_variation_qty', 'total_cumulative')
    def _compute_remaining(self):
        for rec in self:
            rec.remaining = rec.new_variation_qty - rec.total_cumulative

    @api.depends('total_previous', 'total_current')
    def _compute_total_cumulative(self):
        for rec in self:
            rec.total_cumulative = rec.total_previous + rec.total_current

    def _compute_from_button(self):
        for rec in self:
            ok = self.env.context.get('from_button')
            if not ok:
                rec.from_button = False
            else:
                rec.from_button = True

    def action_add(self):
        ipc = self.env['ipc.certificate'].browse(self.env.context.get('active_id'))

        existing_line_ids = set(ipc.line_ids.mapped('source_line_id').ids)

        vals = []

        for line in self:
            if line.id in existing_line_ids:
                continue

            vals.append((0, 0, {
                'items': line.items,
                'uom_id': line.uom_id.id,
                'qty': line.qty,
                'new_variation_qty': line.new_variation_qty,
                'total_previous': line.total_previous,
                'total_current': line.total_current,
                'total_cumulative': line.total_cumulative,
                'unit_price': line.unit_price,
                'remaining': line.remaining,
                'source_line_id': line.id,
            }))

        if vals:
            ipc.write({
                'line_ids': vals
            })

        return {
            'type': 'ir.actions.act_window',
            'name': 'IPCs',
            'res_model': 'ipc.certificate',
            'res_id': ipc.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_request_subcontractor(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "subcontractor.request.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"active_ids": self.ids},
        }

    @api.depends('qty', 'new_variation_qty', 'total_contract_value', 'total_estimated_value', 'unit_price')
    def _compute_surplus_and_deficit(self):
        for rec in self:
            if rec.qty > rec.new_variation_qty:
                rec.surplus_qty = rec.qty - rec.new_variation_qty
                rec.deficit_qty = 0.0
            elif rec.qty < rec.new_variation_qty:
                rec.deficit_qty = rec.new_variation_qty - rec.qty
                rec.surplus_qty = 0.0
            else:
                rec.surplus_qty = 0.0
                rec.deficit_qty = 0.0

            rec.total_contract_value = rec.qty * rec.unit_price
            rec.total_estimated_value = rec.new_variation_qty * rec.unit_price

            if rec.total_contract_value > rec.total_estimated_value:
                rec.surplus_value = rec.total_contract_value - rec.total_estimated_value
                rec.deficit_value = 0.0
            elif rec.total_contract_value < rec.total_estimated_value:
                rec.deficit_value = rec.total_estimated_value - rec.total_contract_value
                rec.surplus_value = 0.0
            else:
                rec.surplus_value = 0.0
                rec.deficit_value = 0.0

    def action_view_sub_items(self):
        self.ensure_one()
        if self.boq_sub_item_id:
            self.boq_sub_item_id.boq_line_id = self.id
            return {
                'name': _('Sub Item'),
                'type': 'ir.actions.act_window',
                'res_model': 'boq.sub.item',
                'view_mode': 'form',
                'res_id': self.boq_sub_item_id.id
            }
        else:
            res = self.env['boq.sub.item'].create({'boq_line_id': self.id})
            self.boq_sub_item_id = res.id
            return {
                'name': _('Sub Item'),
                'type': 'ir.actions.act_window',
                'res_model': 'boq.sub.item',
                'view_mode': 'form',
                'res_id': res.id
            }

    @api.constrains('new_variation_qty', 'unit_price')
    def _check_new_variation_qty(self):
        for rec in self:
            if rec.new_variation_qty <= 0:
                raise UserError(_('New Variation QTY should be greater than zero.'))
            if rec.unit_price <= 0:
                raise UserError(_('Unit Price should be greater than zero.'))
