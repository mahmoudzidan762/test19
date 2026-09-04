from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    bid_file_id = fields.Many2one('bid.file', string='Bid File')
    is_commission = fields.Boolean(string='Is Commission', default=False)
