from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountTaxGroupInherit(models.Model):
    _inherit = 'account.tax.group'

    type = fields.Selection([
        ('tax', 'Tax'),
        ('retention', 'Retention'),
        ('down_payment', 'Down Payment'),
    ], string='Type', default='tax', tracking=True)
