from odoo import models, fields, api, _
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta


class IpcCertificate(models.Model):
    _name = 'ipc.certificate'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Interim Payment Certificate'
    _rec_name = 'name'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    boq_id = fields.Many2one('bill.of.quantity', string="Bill Of Quantity", required=True)
    lead_id = fields.Many2one('crm.lead', string="Project")
    partner_id = fields.Many2one('res.partner', string="Customer")
    project_manager_id = fields.Many2one('hr.employee', string='Project Manager')
    st_date = fields.Date(string='Start Date')
    end_date = fields.Date(string='End Date')
    date_duration = fields.Char(
        compute='_compute_date_duration',
        store=True,
        string='Duration'
    )
    analytic_account_id = fields.Many2one('account.analytic.account')
    invoice_date = fields.Date()
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('approved', 'Approved'),
        ('invoiced', 'Invoiced'),
        ('cancelled', 'Cancelled')
    ], default='draft')
    line_ids = fields.One2many('bill.of.quantity.line', 'ipc_id')
    total_ipc_amount = fields.Float(string="Gross Work Value", compute='_compute_total_ipc_amount', store=True)

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

    @api.depends('line_ids.ipc_total')
    def _compute_total_ipc_amount(self):
        for rec in self:
            rec.total_ipc_amount = sum(line.ipc_total for line in rec.line_ids)

    # ===================== Notes / Attachments =====================
    attachments = fields.Html(string='Attachments')
    notes = fields.Text(string='Notes')

    # ===================== Accounting =====================
    retention_percentage = fields.Float(string="Retention Percentage")
    retention_previous = fields.Float(string="Retention Previous", compute='_compute_retention_previous', store=True)
    retention_current = fields.Float(string="Retention Current", compute='_compute_retention_current', store=True)
    retention_journal = fields.Many2one('account.journal', string="Retention Journal")
    retention_account = fields.Many2one('account.account', string="Retention Account")
    retention_cumulative = fields.Float(string="Retention Accumulative", compute='_compute_retention_cumulative',
                                        store=True)
    advance_percentage = fields.Float(string="Advance Percentage")
    advance_total_amount = fields.Float(string="Advance Total Amount")
    advance_recovered_before = fields.Float(string="Advance Recovered Before",
                                            compute='_compute_advance_recovered_before', store=True)
    advance_recovery_current = fields.Float(string="Advance Recovery Current",
                                            compute='_compute_advance_recovery_current', store=True)
    advance_recovery_cumulative = fields.Float(string="Advance Recovery Accumulative",
                                               compute='_compute_advance_recovery_cumulative', store=True)
    remaining_advance_balance = fields.Float(string="Remaining Advance Balance",
                                             compute='_compute_remaining_advance_balance', store=True)
    advance_journal = fields.Many2one('account.journal', string="Advance Journal")
    advance_account = fields.Many2one('account.account', string="Advance Account")
    penalty_account = fields.Many2one('account.account', string="Penalty Account")
    deduction_account = fields.Many2one('account.account', string="Deduction Account")
    penalty_percentage = fields.Float(string="Penalty Percentage")
    penalty_amount = fields.Float(string="Penalty Amount", compute='_compute_penalty_amount', store=True)
    other_deduction_percentage = fields.Float(string="Other Deduction Percentage")
    other_deduction_amount = fields.Float(string="Other Deduction Amount", compute='_compute_other_deduction_amount',
                                          store=True)
    penalty_journal = fields.Many2one('account.journal', string="Penalty Journal")
    remarks = fields.Text(string="Remarks")

    @api.depends('advance_total_amount', 'advance_recovery_cumulative')
    def _compute_remaining_advance_balance(self):
        for rec in self:
            rec.remaining_advance_balance = rec.advance_total_amount - rec.advance_recovery_cumulative

    @api.depends('advance_recovered_before', 'advance_recovery_current')
    def _compute_advance_recovery_cumulative(self):
        for rec in self:
            rec.advance_recovery_cumulative = rec.advance_recovered_before + rec.advance_recovery_current

    @api.depends('advance_percentage', 'line_ids.ipc_total')
    def _compute_advance_recovered_before(self):
        for rec in self:
            previous_ipc = self.env['ipc.certificate'].search([
                ('boq_id', '=', rec.boq_id.id),
                ('id', '!=', rec.id),
                ('state', '=', 'invoiced')
            ], order='id desc', limit=1)
            rec.advance_recovered_before = (
                    rec.advance_percentage * previous_ipc.total_ipc_amount) if previous_ipc else 0.0

    @api.depends('advance_percentage', 'total_ipc_amount')
    def _compute_advance_recovery_current(self):
        for rec in self:
            rec.advance_recovery_current = rec.advance_percentage * rec.total_ipc_amount

    @api.depends('other_deduction_percentage', 'total_ipc_amount')
    def _compute_other_deduction_amount(self):
        for rec in self:
            rec.other_deduction_amount = rec.other_deduction_percentage * rec.total_ipc_amount

    @api.depends('penalty_percentage', 'total_ipc_amount')
    def _compute_penalty_amount(self):
        for rec in self:
            rec.penalty_amount = rec.penalty_percentage * rec.total_ipc_amount

    @api.depends('retention_previous', 'retention_current')
    def _compute_retention_cumulative(self):
        for rec in self:
            rec.retention_cumulative = rec.retention_previous + rec.retention_current

    @api.depends('retention_percentage', 'line_ids.ipc_total')
    def _compute_retention_previous(self):
        for rec in self:
            previous_ipc = self.env['ipc.certificate'].search([
                ('boq_id', '=', rec.boq_id.id),
                ('id', '!=', rec.id),
                ('state', '=', 'invoiced')
            ], order='id desc', limit=1)
            rec.retention_previous = (
                    rec.retention_percentage * previous_ipc.total_ipc_amount) if previous_ipc else 0.0

    @api.depends('retention_percentage', 'total_ipc_amount')
    def _compute_retention_current(self):
        for rec in self:
            rec.retention_current = rec.retention_percentage * rec.total_ipc_amount

    # ===================== SUMMARY =====================
    previous_ipc_amount = fields.Float(string="Previous IPC Amount", compute='_compute_previous_ipc_amount', store=True)
    net_before_tax = fields.Float(string="Net Before Tax", compute='_compute_net_before_tax', store=True)
    tax_percentage = fields.Float(string="Tax %", default=0.15)
    tax_amount = fields.Float(string="Tax Amount", compute='_compute_tax_amount', store=True)
    final_net_amount = fields.Float(string="Final Net Amount", compute='_compute_final_net_amount', store=True)
    total_deductions = fields.Float(string="Total Deductions", compute='_compute_total_deductions', store=True)

    @api.depends('net_before_tax', 'tax_amount')
    def _compute_final_net_amount(self):
        for rec in self:
            rec.final_net_amount = rec.net_before_tax + rec.tax_amount

    @api.depends('net_before_tax', 'tax_percentage')
    def _compute_tax_amount(self):
        for rec in self:
            rec.tax_amount = (rec.tax_percentage / 100) * rec.net_before_tax

    @api.depends('total_ipc_amount', 'total_deductions')
    def _compute_net_before_tax(self):
        for rec in self:
            rec.net_before_tax = rec.total_ipc_amount - rec.total_deductions

    @api.depends('retention_current', 'advance_recovery_current', 'penalty_amount', 'other_deduction_amount')
    def _compute_total_deductions(self):
        for rec in self:
            rec.total_deductions = rec.retention_current + rec.advance_recovery_current + rec.penalty_amount + rec.other_deduction_amount

    @api.depends('total_ipc_amount')
    def _compute_previous_ipc_amount(self):
        for rec in self:
            previous_ipc = self.env['ipc.certificate'].search([
                ('boq_id', '=', rec.boq_id.id),
                ('id', '!=', rec.id),
                ('state', '=', 'invoiced')
            ], order='id desc', limit=1)
            rec.previous_ipc_amount = previous_ipc.total_ipc_amount if previous_ipc else 0.0

    @api.model
    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]

        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('ipc.certificate') or _('New')

        return super(IpcCertificate, self).create(vals_list)

    def action_add_boq_line(self):
        self.ensure_one()
        return {
            'name': _('Add BOQ Line'),
            'type': 'ir.actions.act_window',
            'res_model': 'bill.of.quantity.line',
            'view_mode': 'list',
            'domain': [('boq_id', '=', self.boq_id.id), ('billed_progress', '<', 1)],
            'context': {'from_button': True}
        }

    # ---------------- STATES ----------------
    def action_confirm(self):
        for rec in self:
            rec.state = 'confirmed'

    def action_approve(self):
        for rec in self:
            rec.state = 'approved'

    def action_invoice(self):
        for rec in self:
            rec.state = 'invoiced'
            for i in rec.line_ids:
                for j in rec.boq_id.boq_line_ids:
                    if i.source_line_id.id == j.id:
                        j.total_previous += i.total_current
                        j.onsite_amount += i.onsite_amount

            sale_journal_id = self.env['account.journal'].search(
                [('type', '=', 'sale')], limit=1
            )

            if not sale_journal_id:
                raise UserError(_('No sales journal found. Please configure one.'))

            view_id = self.env.ref('account.view_move_form').id

            invoice_line_vals = []
            for line in rec.line_ids:
                invoice_line_vals.append((0, 0, {
                    'name': line.items,
                    'quantity': line.total_current,
                    'price_unit': line.unit_price,
                    'currency_id': self.env.company.currency_id.id,
                    'product_uom_id': line.uom_id.id,
                }))
            invoice_line_vals.append((0, 0, {
                'name': f'Retention Deduction - {rec.retention_percentage * 100}%',
                'quantity': 1,
                'price_unit': rec.retention_current * -1,
                'account_id': rec.retention_account.id,
            }))
            invoice_line_vals.append((0, 0, {
                'name': f'Advance Recovery - {rec.advance_percentage * 100}%',
                'quantity': 1,
                'price_unit': rec.advance_recovery_current * -1,
                'account_id': rec.advance_account.id,
            }))
            if rec.penalty_percentage:
                invoice_line_vals.append((0, 0, {
                    'name': f'Delay Penalty - {rec.penalty_percentage}%',
                    'quantity': 1,
                    'price_unit': rec.penalty_amount * -1,
                    'account_id': rec.penalty_account.id,
                }))
            if rec.other_deduction_percentage:
                invoice_line_vals.append((0, 0, {
                    'name': f'Other Deduction - {rec.other_deduction_percentage}%',
                    'quantity': 1,
                    'price_unit': rec.other_deduction_amount * -1,
                    'account_id': rec.deduction_account.id,
                }))

            currency_id = self.env.company.currency_id.id

            account_move_id = self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': rec.partner_id.id,
                'lead_id': rec.lead_id.id,
                'ipc_number': rec.name,
                'journal_id': sale_journal_id.id,
                'currency_id': currency_id,
                'invoice_line_ids': invoice_line_vals,
            })

            return {
                'name': _('IPC Invoice'),
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'view_mode': 'form',
                'view_id': view_id,
                'res_id': account_move_id.id,
            }

    def action_cancel(self):
        for rec in self:
            rec.state = 'cancelled'

    def action_reset_draft(self):
        for rec in self:
            rec.state = 'draft'
