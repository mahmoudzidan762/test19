from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError


class SubContractorRequestWizard(models.TransientModel):
    _name = 'subcontractor.request.wizard'

    partner_id = fields.Many2one('res.partner', string='Subcontractor', domain="[('x_is_subcontractor', '=', True)]",
                                 required=True)
    date_start = fields.Date(string='Start Date', required=True)
    date_end = fields.Date(string='End Date')
    requisition_id = fields.Many2one('purchase.requisition', string='Agreement')
    request_type = fields.Selection([('new', 'New Request'), ('update', 'Update Request')], string='Request Type',
                                    default='new',
                                    required=True)

    def create_request(self):
        active_ids = self.env.context.get('active_ids')
        if not active_ids:
            raise ValidationError("No lines selected.")
        boq_lines = self.env['bill.of.quantity.line'].browse(active_ids)
        if self.request_type == 'new':
            pur_aggr = self.env['purchase.requisition'].create({
                'vendor_id': self.partner_id.id,
                'requisition_type': 'blanket_order',
                'date_start': self.date_start,
                'date_end': self.date_end,
                'reference': boq_lines[0].boq_id.name,
                'lead_id': boq_lines[0].boq_id.lead_id.id if boq_lines[0].boq_id.lead_id else None,
            })
            ProductProduct = self.env['product.product']
            for line in boq_lines:
                product = ProductProduct.search(
                    [('name', '=', line.items)],
                    limit=1
                )
                if not product:
                    product_template = self.env['product.template'].create({
                        'name': line.items,
                        'type': 'service',
                    })
                    product = product_template.product_variant_id

                self.env['purchase.requisition.line'].create({
                    'requisition_id': pur_aggr.id,
                    'product_id': product.id,
                    'product_qty': line.new_variation_qty,
                    'price_unit': line.unit_price,
                })
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'purchase.requisition',
                'res_id': pur_aggr.id,
                'view_mode': 'form',
            }
        else:
            if not self.requisition_id:
                raise UserError(_("Please select a Purchase Agreement for update request."))
            self.requisition_id.write({
                'state': 'draft',
                'vendor_id': self.partner_id.id,
                'date_start': self.date_start,
                'date_end': self.date_end,
                'reference': boq_lines[0].boq_id.name,
            })
            for line in boq_lines:
                req_line = self.env['purchase.requisition.line'].search([
                    ('requisition_id', '=', self.requisition_id.id),
                    ('product_id.name', '=', line.items)
                ], limit=1)
                if req_line:
                    req_line.write({
                        'product_qty': line.new_variation_qty,
                        'price_unit': line.unit_price,
                    })
                else:
                    product = self.env['product.product'].search(
                        [('name', '=', line.items)],
                        limit=1
                    )
                    if not product:
                        product_template = self.env['product.template'].create({
                            'name': line.items,
                            'type': 'service',
                        })
                        product = product_template.product_variant_id

                    self.env['purchase.requisition.line'].create({
                        'requisition_id': self.requisition_id.id,
                        'product_id': product.id,
                        'product_qty': line.new_variation_qty,
                        'price_unit': line.unit_price,
                    })
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'purchase.requisition',
                'res_id': self.requisition_id.id,
                'view_mode': 'form',
            }
