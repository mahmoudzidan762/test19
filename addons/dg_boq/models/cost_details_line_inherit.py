from odoo import models, fields, api, _
from odoo.exceptions import UserError


class CostDetailsLineInherit(models.Model):
    _inherit = 'cost.details.line'

    material_sub_items_details_id = fields.Many2one('boq.sub.item', string='Material Sub Items Details')
    tools_sub_items_details_id = fields.Many2one('boq.sub.item', string='Tools Sub Items Details')
    labor_sub_items_details_id = fields.Many2one('boq.sub.item', string='Labor Sub Items Details')
    delivery_sub_items_details_id = fields.Many2one('boq.sub.item', string='Delivery Sub Items Details')
