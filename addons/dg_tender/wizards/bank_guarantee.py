from odoo import models, fields, api, _
from odoo.exceptions import UserError


class BankGuarantee(models.TransientModel):
    _name = 'bank.guarantee'

    guarantee_type = fields.Selection([
        ('initial', 'Initial Guarantee'),
        ('final', 'Final Guarantee'),
    ])
    project_value = fields.Integer()
    bank_guarantee_percent = fields.Float('Bank Guarantee %')
    bank_guarantee_value = fields.Float()
    payment_method = fields.Char(string='Transaction Type')
    journal_id = fields.Many2one(comodel_name='account.journal', string='Journal', required=True)
    bid_file_id = fields.Many2one('bid.file', string='Bid File')
    ref = fields.Char(string='Ref')
    label = fields.Char(string='Label')
    narration = fields.Html(string='Notes')
    payment_date = fields.Date(string='Payment Date', default=fields.Date.context_today)

    # Commission %
    commission_percent = fields.Float(string='Commission %')
    commission_amount = fields.Float(
        string='Commission Amount',
        compute='_compute_commission_amount',
        store=True,
    )

    @api.depends('commission_percent', 'bank_guarantee_value')
    def _compute_commission_amount(self):
        for rec in self:
            rec.commission_amount = (rec.bank_guarantee_value * (rec.commission_percent / 100)) * 100

    def create_bank_guarantee(self):
        self.ensure_one()
        if self.guarantee_type == 'final':
            statements = self.env['account.bank.statement.line'].search(
                [('bid_file_id', '=', self.bid_file_id.id), ('is_commission', '=', False)])
            for s in statements:
                if s.ref != self.bid_file_id.name:
                    move = s.move_id
                    if move and move.state == 'posted':
                        reversal_wizard = self.env['account.move.reversal'].with_context(
                            active_ids=move.ids,
                            active_model='account.move',
                        ).create({
                            'date': fields.Date.context_today(self),
                            'journal_id': move.journal_id.id,
                            'reason': 'Final Bank Guarantee Reversal',
                        })
                        reversal_wizard.reverse_moves()
        payment_vals = {
            'payment_ref': self.label,
            'partner_id': self.bid_file_id.customer_id.id,
            'narration': self.narration,
            'date': self.payment_date,
            'ref': self.ref,
            'transaction_type': self.payment_method,
            'amount': self.bank_guarantee_value,
            'journal_id': self.journal_id.id,
            'bid_file_id': self.bid_file_id.id,
        }
        self.env['account.bank.statement.line'].create(payment_vals)
        if self.commission_percent > 0:
            commission_vals = {
                'payment_ref': self.label,
                'partner_id': self.bid_file_id.customer_id.id,
                'narration': self.narration,
                'date': self.payment_date,
                'ref': self.ref,
                'transaction_type': self.payment_method,
                'amount': self.commission_amount,
                'journal_id': self.journal_id.id,
                'bid_file_id': self.bid_file_id.id,
                'is_commission': True,
            }
            self.env['account.bank.statement.line'].create(commission_vals)
        return {
            'name': _('Bank Guarantee'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.bank.statement.line',
            'view_mode': 'list',
            'domain': [('bid_file_id', '=', self.bid_file_id.id)],
        }
