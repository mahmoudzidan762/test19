from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ProjectPaymentRequest(models.TransientModel):
    _name = 'project.payment.request'

    payment_for = fields.Selection([
        ('tender_brochure_value', 'Tender Brochure Value'),
        ('tender_insurance_value', 'Tender Insurance Value'),
        ('down_payment_value', 'Down Payment Value'),
        ('business_guarantee_value', 'Business Guarantee Value'),
        ('other_value', 'Other Value'),
    ])
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id
    )
    amount = fields.Monetary(string='Amount', currency_field='currency_id')
    bid_file_id = fields.Many2one('bid.file', string='Ref')
    journal_id = fields.Many2one('account.journal', string='Journal')
    label = fields.Char(string='Label')
    transaction_type = fields.Char(string='Transaction')
    narration = fields.Html(string='Notes')
    payment_date = fields.Date(string='Payment Date', default=fields.Date.context_today)
    payment_type = fields.Selection([
        ('outbound', 'Send'),
        ('inbound', 'Receive'),
    ], string='Payment Type', default='outbound')
    partner_id = fields.Many2one('res.partner', string='Partner')

    @api.onchange('payment_for')
    def _onchange_payment_for(self):
        if self.bid_file_id and self.payment_for:
            if self.payment_for == 'tender_brochure_value':
                self.amount = self.bid_file_id.lead_id.tender_booklet_value
            else:
                self.amount = 0.0

    def create_account_payment(self):
        self.ensure_one()
        payment_vals = {
            'payment_ref': self.label,
            'partner_id': self.bid_file_id.customer_id.id,
            'narration': self.narration,
            'date': self.payment_date,
            'ref': self.bid_file_id.name,
            'transaction_type': self.transaction_type,
            'amount': self.amount,
            'journal_id': self.journal_id.id,
            'bid_file_id': self.bid_file_id.id,
        }
        self.env['account.bank.statement.line'].create(payment_vals)
        self.bid_file_id.state = 'paid'
        return {
            'name': _('Booklet Fee'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.bank.statement.line',
            'view_mode': 'list',
            'domain': [('bid_file_id', '=', self.bid_file_id.id)],
        }
