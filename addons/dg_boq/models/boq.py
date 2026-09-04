from odoo import models, fields, api, _
from dateutil.relativedelta import relativedelta
import logging

logger = logging.getLogger(__name__)


class BillOfQuantity(models.Model):
    _name = 'bill.of.quantity'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Bill of Quantity'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    estimation_id = fields.Many2one('estimation', string='Estimation')
    lead_id = fields.Many2one('crm.lead', string='Project', related='estimation_id.lead_id', store=True)
    partner_id = fields.Many2one('res.partner', string='Customer', related='estimation_id.partner_id', store=True)
    sale_order_id = fields.Many2one('sale.order', string='Quotation', related='estimation_id.sale_order_id', store=True)
    project_manager_id = fields.Many2one('hr.employee', string='Project Manager')
    st_date = fields.Date(string='Start Date', related='estimation_id.st_date', store=True)
    end_date = fields.Date(string='End Date', related='estimation_id.end_date', store=True)
    date_duration = fields.Char(
        compute='_compute_date_duration',
        store=True,
        string='Duration'
    )
    billed_progress = fields.Float(string='Billed Progress %', default=0.0, compute='_compute_billed_progress',
                                   store=True)
    onsite_progress = fields.Float(string='Onsite Progress %', default=0.0, compute='_compute_onsite_progress',
                                   store=True)
    state = fields.Selection([
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', readonly=True, default='in_progress', tracking=True)
    boq_line_ids = fields.One2many('bill.of.quantity.line', 'boq_id', string='BOQ Lines')
    retention_percent = fields.Float(string='Retention %')
    retention_journal_id = fields.Many2one('account.journal', string='Retention Journal')
    retention_amount_total = fields.Float(string='Total Retention Amount')
    advanced_payment_journal_id = fields.Many2one('account.journal', string='Advanced Payment Journal')
    advanced_payment_amount = fields.Float(string='Advanced Payment Amount')
    advanced_payment_percent = fields.Float(string='Advanced Payment %', compute='_compute_advanced_payment_percent',
                                            store=True)
    outstanding_advanced_payment_amount = fields.Float(string='Outstanding Advanced Payment Amount')
    outstanding_advanced_payment_percent = fields.Float(string='Outstanding Advanced Payment %')
    variation_count = fields.Integer(string='Variation Orders', compute='_compute_variation_count')
    po_count = fields.Integer(string='Purchase Orders', compute='_compute_po_count')
    payment_count = fields.Integer(string='IPCs', compute='_compute_payment_count')

    @api.depends('advanced_payment_amount', 'estimation_id.sale_order_id.amount_total')
    def _compute_advanced_payment_percent(self):
        for rec in self:
            total_contract_amount = 1.0
            if rec.estimation_id.sale_order_id.amount_total:
                total_contract_amount = rec.estimation_id.sale_order_id.amount_total
            rec.advanced_payment_percent = rec.advanced_payment_amount / total_contract_amount

    @api.depends('boq_line_ids.onsite_amount', 'boq_line_ids.new_variation_qty')
    def _compute_onsite_progress(self):
        for rec in self:
            total_onsite_amount = sum(line.onsite_amount for line in rec.boq_line_ids)
            total_new_variation = sum(line.new_variation_qty for line in rec.boq_line_ids)
            if total_onsite_amount and total_new_variation:
                rec.onsite_progress = total_onsite_amount / total_new_variation

    @api.depends('boq_line_ids.total_previous', 'boq_line_ids.new_variation_qty')
    def _compute_billed_progress(self):
        for rec in self:
            total_previous = sum(line.total_previous for line in rec.boq_line_ids)
            total_new_variation = sum(line.new_variation_qty for line in rec.boq_line_ids)
            if total_previous and total_new_variation:
                rec.billed_progress = total_previous / total_new_variation

    def action_create_ipc(self):
        for rec in self:
            return {
                'name': _('IPCs'),
                'type': 'ir.actions.act_window',
                'res_model': 'ipc.certificate',
                'view_mode': 'form',
                'target': 'current',
                'context': {
                    'default_boq_id': rec.id,
                    'default_lead_id': rec.lead_id.id,
                    'default_partner_id': rec.partner_id.id,
                    'default_project_manager_id': rec.project_manager_id.id,
                    'default_st_date': rec.st_date,
                    'default_end_date': rec.end_date,
                    'default_date_duration': rec.date_duration,
                    'default_retention_percentage': rec.retention_percent,
                    'default_advance_percentage': rec.advanced_payment_percent,
                    'default_advance_total_amount': rec.advanced_payment_amount,
                    'default_retention_journal': rec.retention_journal_id.id,
                    'default_advance_journal': rec.advanced_payment_journal_id.id,
                }
            }

    @api.depends('st_date', 'end_date')
    def _compute_date_duration(self):
        for rec in self:
            if rec.st_date and rec.end_date:
                delta = relativedelta(
                    rec.end_date, rec.st_date
                )
                rec.date_duration = (
                    f"{delta.years} Years, "
                    f"{delta.months} Months, "
                    f"{delta.days} Days"
                )
            else:
                rec.date_duration = False

    def _compute_variation_count(self):
        for rec in self:
            rec.variation_count = self.env['variation.order'].search_count([('boq_id', '=', rec.id)])

    def _compute_po_count(self):
        for rec in self:
            rec.po_count = self.env['material.purchase.requisition'].search_count(
                [('boq_sub_item_id', 'in', rec.boq_line_ids.mapped('boq_sub_item_id').ids),
                 ('state', '=', 'purchase_order_created'), ])

    def _compute_payment_count(self):
        for rec in self:
            rec.payment_count = self.env['ipc.certificate'].search_count([('boq_id', '=', rec.id)])

    @api.model
    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]

        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('bill.of.quantity') or _('New')

        return super(BillOfQuantity, self).create(vals_list)

    def action_cancel(self):
        self.state = 'cancel'

    def action_done(self):
        self.state = 'done'

    def action_open_payments(self):
        return {
            'name': _('IPCs'),
            'type': 'ir.actions.act_window',
            'res_model': 'ipc.certificate',
            'view_mode': 'list,form',
            'domain': [('boq_id', '=', self.id)],
        }

    def action_open_purchase_requisitions(self):
        for rec in self:
            return {
                'name': _('Purchase Requisitions'),
                'type': 'ir.actions.act_window',
                'res_model': 'material.purchase.requisition',
                'view_mode': 'list,form',
                'domain': [
                    ('boq_sub_item_id', 'in', rec.boq_line_ids.mapped('boq_sub_item_id').ids),
                    ('state', '=', 'purchase_order_created'),
                ],
                'target': 'current',
            }

    def action_request_variation_order(self):
        for rec in self:
            vo_seq = self.env['ir.sequence'].next_by_code('variation.order')
            full_seq = f"{rec.name}/{vo_seq}"
            vo_rec = self.env['variation.order'].create({
                'name': full_seq,
                'boq_id': rec.id,
            })
            vo_lines = []
            for line in rec.boq_line_ids:
                vals = line.copy_data()[0]
                vals.update({
                    'boq_id': False,
                    'variation_id': vo_rec.id,
                    'origin_line_id': line.id,
                })
                vo_lines.append((0, 0, vals))
            vo_rec.boq_line_ids = vo_lines
            return {
                'name': _('Variation Order'),
                'type': 'ir.actions.act_window',
                'res_model': 'variation.order',
                'view_mode': 'form',
                'res_id': vo_rec.id,
            }

    def action_open_variation_orders(self):
        for rec in self:
            return {
                'name': _('Variation Orders'),
                'type': 'ir.actions.act_window',
                'res_model': 'variation.order',
                'view_mode': 'list,form',
                'domain': [('boq_id', '=', rec.id)],
            }
