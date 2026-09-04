from odoo import models, fields, api, _
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta
import logging

logger = logging.getLogger(__name__)


class Estimation(models.Model):
    _name = 'estimation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Estimation'

    name = fields.Char(string='Reference', required=True,
                       copy=False, readonly=True,
                       default=lambda self: _('New'))
    lead_id = fields.Many2one('crm.lead', string='Project Name')
    sale_order_id = fields.Many2one('sale.order', string='Quotation')
    partner_id = fields.Many2one('res.partner', string='Customer', related='lead_id.partner_id', store=True,
                                 required=True)
    direct_cost_line_ids = fields.One2many('direct.cost.line', 'estimation_id')
    indirect_cost_line_ids = fields.One2many('indirect.cost.line', 'estimation_id')
    indirect_cost_summary_line_ids = fields.One2many('indirect.cost.summary.line', 'estimation_id')
    quotation_line_ids = fields.One2many('quotation.line', 'estimation_id')
    margin = fields.Float(string='Margin %', store=True, default=0.0)
    overhead = fields.Float(string='Overhead %', store=True, default=0.0)
    st_date = fields.Date(string='Start Date')
    end_date = fields.Date(string='End Date')
    date_duration = fields.Char(
        compute='_compute_date_duration',
        store=True,
        string='Duration'
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('estimation_prepared', 'Estimation Prepared'),
        ('quotation_created', 'Quotation Created'),
        ('contract', 'Contract'),
        ('boq_created', 'Bill Of Quantity Created'),
    ], string='Status', readonly=True, default='draft', tracking=True)
    total_indirect_estimation = fields.Float(string='Total In-Direct Estimation',
                                             compute='_compute_total_indirect_estimation', store=True)
    total_direct_estimation = fields.Float(string='Total Direct Estimation', compute='_compute_total_direct_estimation',
                                           store=True)

    def action_apply_overhead(self):
        for rec in self:
            for line in rec.direct_cost_line_ids:
                if line.type_of_implement != 'running':
                    line.overhead = rec.overhead

    def action_apply_margin(self):
        for rec in self:
            for line in rec.direct_cost_line_ids:
                if line.type_of_implement != 'running':
                    line.margin = rec.margin

    @api.depends('st_date', 'end_date')
    def _compute_date_duration(self):
        for rec in self:
            if rec.st_date and rec.end_date:
                delta = relativedelta(
                    rec.end_date, rec.st_date
                )
                rec.date_duration = (
                    f"{delta.years} Years, "
                    f"{delta.months} Months, "
                    f"{delta.days} Days"
                )
            else:
                rec.date_duration = False

    @api.constrains('st_date', 'end_date')
    def _check_dates(self):
        for rec in self:
            if rec.st_date and rec.end_date and rec.end_date < rec.st_date:
                raise UserError(_('End Date cannot be Before Start Date.'))

    @api.depends('indirect_cost_line_ids.total')
    def _compute_total_indirect_estimation(self):
        for estimation in self:
            total = sum(line.total for line in estimation.indirect_cost_line_ids)
            estimation.total_indirect_estimation = total

    @api.depends('direct_cost_line_ids.total_no_tax')
    def _compute_total_direct_estimation(self):
        for estimation in self:
            total = sum(line.total_no_tax for line in estimation.direct_cost_line_ids)
            estimation.total_direct_estimation = total

    @api.model
    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]

        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('estimation') or _('New')

        return super(Estimation, self).create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        if 'indirect_cost_line_ids' in vals:
            self.indirect_cost_summary_line_ids = [(5, 0, 0)]
            for rec in self:
                exist = []
                for line in rec.indirect_cost_line_ids:
                    if line.category_id.id not in exist:
                        exist.append(line.category_id.id)
                        self.env['indirect.cost.summary.line'].create({
                            'category_id': line.category_id.id,
                            'estimation_id': line.estimation_id.id,
                        })
        return res

    def action_prepare_estimation(self):
        for rec in self:
            rec.state = 'estimation_prepared'

            lines_vals = []

            for line in rec.direct_cost_line_ids:
                lines_vals.append((0, 0, {
                    'estimation_id': rec.id,
                    'items': line.items,
                    'uom_id': line.uom_id.id,
                    'qty': line.qty,
                    'unit_price': line.total_cost_unit,
                    'total_unit_price': line.total_no_tax,
                    'tax_ids': line.tax_ids.id,
                    'total_price': line.final_total,
                }))

            rec.quotation_line_ids = [(5, 0, 0)] + lines_vals

    def action_create_quotation(self):
        for rec in self:
            rec.state = 'quotation_created'
            quotation_vals = {
                'estimation_id': rec.id,
                'partner_id': rec.partner_id.id,
            }
            lines = []
            if not rec.end_date:
                raise UserError(_('Please set End Date for the Estimation before creating Quotation.'))
            project_template_id = self.env['project.project'].create({
                'name': rec.lead_id.name,
                'allow_task_dependencies': True,
                'allow_milestones': True,
                'date_start': rec.st_date,
                'date': rec.end_date,
            })
            estimation_product_rec = self.env['product.product'].create({
                'name': rec.lead_id.name,
                'type': 'service',
                'service_tracking': 'project_only',
                'project_template_id': project_template_id.id,
            })
            for line in rec.quotation_line_ids:
                lines.append((0, 0, {
                    'product_id': estimation_product_rec.id,
                    'name': line.items,
                    'product_uom_id': line.uom_id.id,
                    'product_uom_qty': line.qty,
                    'price_unit': line.unit_price,
                    'tax_ids': [(6, 0, line.tax_ids.ids)],
                    'price_subtotal': line.total_price,
                }))
            quotation_vals['order_line'] = lines
            quotations = self.env['sale.order'].search([('estimation_id', '=', rec.id)])
            for q in quotations:
                q.action_cancel()
            quotation = self.env['sale.order'].create(quotation_vals)
            rec.sale_order_id = quotation.id

    def action_create_boq(self):
        for rec in self:
            rec.state = 'boq_created'
            boq_rec = self.env['bill.of.quantity'].create({'estimation_id': rec.id})
            boq_lines_vals = []
            for line in rec.direct_cost_line_ids:
                boq_sub_item = False
                if line.type_of_implement == 'inhouse' and line.cost_details_id:
                    boq_sub_item = self.env['boq.sub.item'].create({
                        'material_cost_ids': [(6, 0, line.cost_details_id.material_cost_ids.ids)],
                        'tools_cost_ids': [(6, 0, line.cost_details_id.tools_cost_ids.ids)],
                        'labor_cost_ids': [(6, 0, line.cost_details_id.labor_cost_ids.ids)],
                        'delivery_cost_ids': [(6, 0, line.cost_details_id.delivery_cost_ids.ids)],
                    })
                boq_lines_vals.append((0, 0, {
                    'items': line.items,
                    'name': line.description,
                    'uom_id': line.uom_id.id,
                    'qty': line.qty,
                    'new_variation_qty': line.qty,
                    'type_of_implement': line.type_of_implement,
                    'margin': line.margin,
                    'overhead': line.overhead,
                    'unit_price': line.total_cost_unit,
                    'boq_sub_item_id': boq_sub_item.id if boq_sub_item else False,
                }))
            boq_rec.boq_line_ids = boq_lines_vals
            return {
                'type': 'ir.actions.act_window',
                'name': 'Bill of Quantity',
                'res_model': 'bill.of.quantity',
                'view_mode': 'form',
                'res_id': boq_rec.id,
            }

    def action_reset_to_draft(self):
        self.state = 'draft'

    def action_open_quotation(self):
        for rec in self:
            if not rec.sale_order_id:
                raise UserError(_('No quotations found for this Estimation.'))
            return {
                'type': 'ir.actions.act_window',
                'name': 'Quotations',
                'res_model': 'sale.order',
                'view_mode': 'list,form',
                'domain': [
                    ('estimation_id', '=', rec.id)
                ],
                'context': {
                    'search_default_draft': 1
                }
            }
