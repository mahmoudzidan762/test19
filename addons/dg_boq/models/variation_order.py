from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

logger = logging.getLogger(__name__)

VAT_RATE = 0.15  # 15% VAT — adjust if needed


class VariationOrder(models.Model):
    _name = 'variation.order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Variation Order'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    boq_id = fields.Many2one('bill.of.quantity', string='Bill Of Quantity', required=True)
    lead_id = fields.Many2one('crm.lead', string='Project', related='boq_id.lead_id', store=True)
    requested_by = fields.Many2one('res.users', string='Variation Order Requested By',
                                   default=lambda self: self.env.user)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('waiting_approval', 'Waiting Approval'),
        ('updated', 'Approved'),
        ('rejected', 'Rejected'),
        ('boq_updated', 'Bill Of Quantity Updated'),
    ], default='draft', tracking=True)
    boq_line_ids = fields.One2many('bill.of.quantity.line', 'variation_id', string='BOQ Lines')
    st_date = fields.Date(string='Start Date', related='boq_id.st_date', store=True)
    end_date = fields.Date(string='New End Date')

    # ─── Summary: raw totals (excl. VAT) ───────────────────────────────────────

    total_surplus_excl_vat = fields.Float(
        string='Total Surplus (excl. VAT)',
        compute='_compute_summary',
        store=True,
        digits=(16, 2),
    )
    total_deficit_excl_vat = fields.Float(
        string='Total Deficit (excl. VAT)',
        compute='_compute_summary',
        store=True,
        digits=(16, 2),
    )

    # ─── Summary: VAT amounts ──────────────────────────────────────────────────

    vat_on_surplus = fields.Float(
        string='VAT on Surplus',
        default=VAT_RATE,
        readonly=True,
    )
    vat_on_deficit = fields.Float(
        string='VAT on Deficit',
        default=VAT_RATE,
        readonly=True,
    )

    # ─── Summary: totals incl. VAT ─────────────────────────────────────────────

    total_surplus_incl_vat = fields.Float(
        string='Total Surplus (incl. VAT)',
        compute='_compute_summary',
        store=True,
        digits=(16, 2),
    )
    total_deficit_incl_vat = fields.Float(
        string='Total Deficit (incl. VAT)',
        compute='_compute_summary',
        store=True,
        digits=(16, 2),
    )

    # ─── Summary: contract & project value ────────────────────────────────────

    original_contract_value = fields.Float(
        string='Original Contract Value (incl. VAT)',
        compute='_compute_summary',
        store=True,
        digits=(16, 2),
    )
    project_value_after_vo = fields.Float(
        string='Project Value after VO (incl. VAT)',
        compute='_compute_summary',
        store=True,
        digits=(16, 2),
        help='Original contract value − deficit incl. VAT + surplus incl. VAT.',
    )
    project_value_after_vo_pct = fields.Float(
        string='Project Value after VO %',
        compute='_compute_summary',
        store=True,
        digits=(16, 2),
        help='project_value_after_vo as a percentage of original_contract_value.',
    )

    # ─── Summary: saving ──────────────────────────────────────────────────────

    total_saving = fields.Float(
        string='Total Saving (incl. VAT)',
        compute='_compute_summary',
        store=True,
        digits=(16, 2),
    )
    total_saving_pct = fields.Float(
        string='Total Saving %',
        compute='_compute_summary',
        store=True,
        digits=(16, 2),
        help='total_saving as a percentage of original_contract_value.',
    )

    # ─── Compute ───────────────────────────────────────────────────────────────

    @api.depends(
        'boq_line_ids.surplus_value',
        'boq_line_ids.deficit_value',
        'boq_id.boq_line_ids.total_contract_value',
    )
    def _compute_summary(self):
        for rec in self:
            lines = rec.boq_line_ids

            # Raw surplus / deficit from the VO lines
            surplus_ex = sum(lines.mapped('surplus_value'))
            deficit_ex = sum(lines.mapped('deficit_value'))

            rec.total_surplus_excl_vat = surplus_ex
            rec.total_deficit_excl_vat = deficit_ex

            # Incl. VAT
            surplus_incl = surplus_ex * (1 + VAT_RATE)
            deficit_incl = deficit_ex * (1 + VAT_RATE)
            rec.total_surplus_incl_vat = surplus_incl
            rec.total_deficit_incl_vat = deficit_incl

            # Original contract value
            quotation_lines = rec.boq_id.estimation_id.quotation_line_ids
            contract_value = sum(quotation_lines.mapped('total_price'))
            rec.original_contract_value = contract_value

            # Saving
            saving = abs(surplus_incl - deficit_incl)
            rec.total_saving = saving

            # Project value after VO
            vo_value = contract_value - saving
            rec.project_value_after_vo = vo_value

            # 6. Percentages (guard against zero division)
            if contract_value:
                rec.project_value_after_vo_pct = (vo_value / contract_value) * 100
            else:
                rec.project_value_after_vo_pct = 0.0

            if contract_value:
                rec.total_saving_pct = (saving / contract_value) * 100
            else:
                rec.total_saving_pct = 0.0

    @api.constrains('st_date', 'end_date')
    def _check_dates(self):
        for rec in self:
            if rec.st_date and rec.end_date and rec.end_date < rec.st_date:
                raise UserError(_('End Date cannot be Before Start Date.'))

    def action_request_approval(self):
        self.ensure_one()
        self.state = 'waiting_approval'

    def action_approved(self):
        self.ensure_one()
        self.state = 'updated'

    def action_rejected(self):
        self.ensure_one()
        self.state = 'rejected'

    def action_set_to_draft(self):
        self.ensure_one()
        self.state = 'draft'

    def action_update_boq(self):
        for vo in self:
            vo.state = 'boq_updated'
            boq = vo.boq_id
            boq.end_date = vo.end_date
            for vo_line in vo.boq_line_ids:
                if vo_line.origin_line_id:
                    boq_line = vo_line.origin_line_id
                    boq_line.write({
                        'new_variation_qty': vo_line.new_variation_qty,
                        'type_of_implement': vo_line.type_of_implement,
                    })
                else:
                    boq.boq_line_ids.create({
                        'boq_id': boq.id,
                        'items': vo_line.items,
                        'uom_id': vo_line.uom_id.id,
                        'new_variation_qty': vo_line.new_variation_qty,
                        'type_of_implement': vo_line.type_of_implement,
                    })
