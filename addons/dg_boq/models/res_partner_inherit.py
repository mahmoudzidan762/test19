from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ResPartnerInherit(models.Model):
    _inherit = 'res.partner'

    x_is_subcontractor = fields.Boolean(string='Is Subcontractor', default=False)
    # x_is_customer = fields.Boolean(string='Is Customer', default=False)
    # x_commercial_registration_number = fields.Float(string='Commercial registration number')
