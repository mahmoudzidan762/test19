from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountMoveInherit(models.Model):
    _inherit = 'account.move'

    lead_id = fields.Many2one('crm.lead', string="Project")
    ipc_number = fields.Char(string="IPC Number")


