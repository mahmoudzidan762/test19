from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_material = fields.Boolean(string='Material', default=False)
    is_tools = fields.Boolean(string='Tools', default=False)
    is_labor = fields.Boolean(string='Labor', default=False)
    is_delivery = fields.Boolean(string='Delivery', default=False)
