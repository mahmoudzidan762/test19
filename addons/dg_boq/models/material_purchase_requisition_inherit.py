from odoo import models, fields, api, _
from odoo.exceptions import UserError


class MaterialRequisition(models.Model):
    _inherit = 'material.purchase.requisition'

    boq_sub_item_id = fields.Many2one('boq.sub.item', string='Bill Of Quantity Sub Item', readonly=True)
    lead_id = fields.Many2one('crm.lead', string='Project')
    sequence = fields.Char(string='Sequence', related='boq_sub_item_id.sequence', store=True)
    item = fields.Char(string='Item', related='boq_sub_item_id.item', store=True)
