from odoo import models, fields, api, _
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError


class BidFile(models.Model):
    _name = 'bid.file'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Bid File'

    name = fields.Char(string='Reference', required=True,
                       copy=False, readonly=True,
                       default=lambda self: _('New'))
    lead_id = fields.Many2one('crm.lead', string='Lead', required=True)
    lead_source = fields.Char(string='Lead Source')
    state = fields.Selection([
        ('submitted', 'Submitted'),
        ('request_for_approval', 'Request For Approval'),
        ('paid', 'Paid Booklet Fee'),
        ('estimated', 'Estimated'),
        ('project', 'Project Created'),
        ('rejected', 'Rejected'),
    ], default='submitted', tracking=True)
    customer_responsible_person_id = fields.Many2one(
        'res.partner',
        string="Customer's Responsible Person",
        store=True,
        readonly=True,
        related='lead_id.customer_responsible_person_id'
    )
    phone = fields.Char(
        readonly=True,
        related='lead_id.phone'
    )
    mobile = fields.Char(
        readonly=True,
        related='lead_id.mobile'
    )
    email = fields.Char(
        readonly=True,
        related='lead_id.email'
    )
    advisor_id = fields.Many2one(
        'hr.employee',
        string='Name',
    )
    advisor_phone = fields.Char(related='advisor_id.work_phone')
    advisor_email = fields.Char(related='advisor_id.work_email')
    advisor_address_id = fields.Many2one('res.partner', related='advisor_id.address_id', string='Work Address')
    contracting_party = fields.Selection(string="Contracting Party",
                                         selection=[('direct_with_employer', 'Direct with Employer'), (
                                             'direct_with_project_contractor', 'Direct  With Project Contractor')],
                                         related='lead_id.contracting_party', readonly=True)

    contracting_agreement = fields.Selection(string="Contracting Agreement", selection=[('tender', 'tender'), (
        'assignment_by_direct_order', 'Assignment by Direct Order')], related='lead_id.contracting_agreement',
                                             readonly=True)

    contract_term_type = fields.Selection(string="Contract Term Type",
                                          selection=[('long_term_contract', 'Long Term Contract'),
                                                     ('short_term_contract', 'Short Term Contract')],
                                          related='lead_id.contract_term_type', readonly=True)

    contract_type = fields.Selection([
        ('unit_price', 'Unit Price Contracts'),
        ('lump_sum', 'Lump Sum Contracts'),
        ('cost_plus', 'Cost-Plus Contracts'),
        ('target_cost', 'Target Cost Contracts'),
        ('non_profit', 'Non Profit Contract'),
        ('other', 'Other'),
    ])
    project_type = fields.Selection([
        ('building', 'Building'),
        ('road', 'Road'),
    ])
    surveying_method = fields.Char(string='Surveying Method')

    # -------------------------
    # Bid Description
    # -------------------------
    bid_description = fields.Html(string='Bid Description')

    # -------------------------
    # Bid Information (Dates)
    # -------------------------
    customer_id = fields.Many2one('res.partner', string='Customer Name', related='lead_id.partner_id', readonly=True)
    contractor_id = fields.Many2one('res.partner', string='Contractor Name')
    bid_name = fields.Char(
        readonly=True,
        related='lead_id.project_name'
    )
    bid_code = fields.Char(
        readonly=True,
        related='lead_id.project_code'
    )
    street = fields.Char()
    street2 = fields.Char()
    city = fields.Char()
    scope_type = fields.Selection([
        ('general_contracting', 'General Contracting'),
        ('renovation', 'Renovation'),
        ('operation_maintenance', 'Operation & Maintenance'),
        ('studying_consultancy', 'Studying & Consultancy'),
    ], string='Scope Type')
    bid_booklet_fee = fields.Float(string='Bid Booklet Fee', related='lead_id.tender_booklet_value', readonly=True)
    last_date_to_submit = fields.Date('Last Date to Submit the Bid')
    opening_bid_date = fields.Date('Opening Bid Date')
    start_date = fields.Date('Project Start Date')
    end_date = fields.Date('Project End Date')
    project_duration = fields.Char(
        compute='_compute_project_duration',
        store=True,
        string='Project Duration'
    )
    site_inspection_date = fields.Date('Site Inspection Date')
    bid_link = fields.Char(string="Bid Link")

    # -------------------------
    # Bid Tech Info
    # -------------------------
    drawing_receiving_date = fields.Date()
    site_receiving_date = fields.Date()
    site_prepare_start = fields.Date(string='Site Preparation Start Date')
    other_attachment = fields.Html('Other Bid Document')
    contract_attachment = fields.Html('Contract Bid Document')
    site_delivering_date = fields.Date()
    actual_start = fields.Date('Bid Actual Start Date')

    # -------------------------
    # Bid Financial Info
    # -------------------------
    bid_estimated_value = fields.Integer()
    tender_booklet_value = fields.Float(related='lead_id.tender_booklet_value')
    tender_booklet_pay_date = fields.Date()
    bank_guarantee_date = fields.Date()
    bid_capital_budget = fields.Float()

    bank_guarantee_percent = fields.Float()
    bank_guarantee_value = fields.Float(compute='_compute_bank_guarantee_value', store=True)
    final_bank_guarantee_percent = fields.Float()
    final_bank_guarantee_value = fields.Float(compute='_compute_final_bank_guarantee_value', store=True)

    bid_inhouse_percent = fields.Float()
    bid_inhouse_value = fields.Float(compute='_compute_inhouse_value', store=True)

    bid_subcontractor_percent = fields.Float()
    bid_subcontractor_value = fields.Float(compute='_compute_subcontractor_value', store=True)

    mobilization_value = fields.Float(compute='_compute_mobilization_value', store=True)
    bid_assets_value = fields.Float()
    bid_capex_value = fields.Float(compute='_compute_bid_capex_value', store=True)
    bid_operation_estimation = fields.Float()
    capex_investment_duration = fields.Selection([
        ('one', '1 Months'),
        ('two', '2 Months'),
        ('three', '3 Months'),
        ('four', '4 Months'),
        ('five', '5 Months'),
        ('six', '6 Months'),
        ('seven', '7 Months'),
        ('eight', '8 Months'),
        ('nine', '9 Months'),
        ('ten', '10 Months'),
        ('eleven', '11 Months'),
        ('twelve', '12 Months'),
        ('thirteen', '13 Months'),
        ('fourteen', '14 Months'),
        ('fifteen', '15 Months'),
        ('sixteen', '16 Months'),
        ('seventeen', '17 Months'),
        ('eighteen', '18 Months'),
        ('nineteen', '19 Months'),
        ('twenty', '20 Months'),
        ('twenty_one', '21 Months'),
        ('twenty_two', '22 Months'),
        ('twenty_three', '23 Months'),
        ('twenty_four', '24 Months'),
    ])
    # mobilization_percent = fields.Float(compute='_compute_mobilization_percent', store=True)

    risk_percent = fields.Float()
    risk_value = fields.Float(compute='_compute_risk_value', store=True)

    retention_percent = fields.Float()
    retention_value = fields.Float(compute='_compute_retention_value', store=True)
    can_approve = fields.Boolean(compute='detect_who_can_approve')

    @api.depends('lead_id.project_category')
    def detect_who_can_approve(self):
        user = self.env.user
        project_category = self.lead_id.project_category
        if project_category == 'heritage':
            if user.id == 2:
                self.can_approve = True
            else:
                self.can_approve = False
        else:
            if user.id == 2:
                self.can_approve = False
            else:
                self.can_approve = True

    def action_reject_for_approval(self):
        for rec in self:
            rec.state = 'rejected'

    def action_request_for_approval(self):
        for rec in self:
            rec.state = 'request_for_approval'

    @api.depends('bid_assets_value', 'bid_operation_estimation')
    def _compute_mobilization_value(self):
        for rec in self:
            rec.mobilization_value = rec.bid_assets_value + rec.bid_operation_estimation

    @api.depends('bank_guarantee_value', 'mobilization_value', 'bid_assets_value', 'bid_operation_estimation')
    def _compute_bid_capex_value(self):
        for rec in self:
            rec.bid_capex_value = rec.bank_guarantee_value + rec.mobilization_value + rec.bid_assets_value + rec.bid_operation_estimation

    @api.model
    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]

        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('bid.file') or _('New')

        return super(BidFile, self).create(vals_list)

    @api.depends('bank_guarantee_percent', 'bid_estimated_value')
    def _compute_bank_guarantee_value(self):
        for rec in self:
            if rec.bank_guarantee_percent and rec.bid_estimated_value:
                rec.bank_guarantee_value = ((rec.bank_guarantee_percent / 100) * rec.bid_estimated_value) * 100
            else:
                rec.bank_guarantee_value = 0.0

    @api.depends('final_bank_guarantee_percent', 'bid_estimated_value')
    def _compute_final_bank_guarantee_value(self):
        for rec in self:
            if rec.final_bank_guarantee_percent and rec.bid_estimated_value:
                rec.final_bank_guarantee_value = ((
                                                          rec.final_bank_guarantee_percent / 100) * rec.bid_estimated_value) * 100
            else:
                rec.final_bank_guarantee_value = 0.0

    @api.depends('bid_inhouse_percent', 'bid_estimated_value')
    def _compute_inhouse_value(self):
        for rec in self:
            if rec.bid_inhouse_percent and rec.bid_estimated_value:
                rec.bid_inhouse_value = ((rec.bid_inhouse_percent / 100) * rec.bid_estimated_value) * 100
            else:
                rec.bid_inhouse_value = 0.0

    @api.depends('bid_subcontractor_percent', 'bid_estimated_value')
    def _compute_subcontractor_value(self):
        for rec in self:
            if rec.bid_subcontractor_percent and rec.bid_estimated_value:
                rec.bid_subcontractor_value = ((rec.bid_subcontractor_percent / 100) * rec.bid_estimated_value) * 100
            else:
                rec.bid_subcontractor_value = 0.0

    @api.depends('risk_percent', 'bid_estimated_value')
    def _compute_risk_value(self):
        for rec in self:
            if rec.risk_percent and rec.bid_estimated_value:
                rec.risk_value = ((rec.risk_percent / 100) * rec.bid_estimated_value) * 100
            else:
                rec.risk_value = 0.0

    @api.depends('retention_percent', 'bid_estimated_value')
    def _compute_retention_value(self):
        for rec in self:
            if rec.retention_percent and rec.bid_estimated_value:
                rec.retention_value = ((rec.retention_percent / 100) * rec.bid_estimated_value) * 100
            else:
                rec.retention_value = 0.0

    @api.constrains('bid_inhouse_percent', 'bid_subcontractor_percent')
    def _check_bid_percentages(self):
        for rec in self:
            total_percent = ((rec.bid_inhouse_percent or 0.0) + (rec.bid_subcontractor_percent or 0.0)) * 100
            if total_percent > 100:
                raise ValidationError(
                    _('The sum of In-House and Subcontractor percentages cannot exceed 100%%. Current total: %.2f%%') % total_percent
                )

    # -------------------------
    # Rules
    # -------------------------
    customer_deduction_ids = fields.One2many(
        'project.customer.deduction', 'bid_file_id', string='Project Customer Deductions'
    )
    subcontract_deduction_ids = fields.One2many(
        'project.subcontract.deduction', 'bid_file_id'
    )
    down_payment_customer_type = fields.Selection([
        ('amount', 'Amount'),
        ('percent', 'Percentage')
    ])
    down_payment_customer_value = fields.Float()
    down_payment_subcontract_type = fields.Selection([
        ('amount', 'Amount'),
        ('percent', 'Percentage')
    ])
    down_payment_subcontract_value = fields.Float()

    # -------------------------
    # Addition
    # -------------------------
    customer_addition_ids = fields.One2many(
        'project.customer.addition', 'bid_file_id', string='Project Customer Addition'
    )
    subcontract_addition_ids = fields.One2many(
        'project.subcontract.addition', 'bid_file_id', string='Project Subcontract Addition'
    )

    # -------------------------
    # Pricing
    # -------------------------
    vat = fields.Float()
    risks = fields.Float()
    additional_expenses = fields.Float()
    margin = fields.Float()

    # -------------------------
    # Document Priority
    # -------------------------
    document_priority = fields.Selection([
        ('papers', 'Papers'),
        ('drawings', 'Drawings')
    ])

    # -------------------------
    # Document Priority
    # -------------------------
    client_type = fields.Selection(
        selection=[
            ('government', 'Government'),
            ('semi_gov', 'Semi-Government'),
            ('private', 'Private'),
            ('developer', 'Developer'),
        ],
        string="Client Type",
        tracking=True,
    )
    payment_reputation = fields.Selection(
        selection=[
            ('strong', 'Strong'),
            ('stable', 'Stable'),
            ('weak', 'Weak'),
            ('risky', 'Risky'),
        ],
        string="Payment Reputation",
        tracking=True,
    )
    funding_source = fields.Selection(
        selection=[
            ('self_funded', 'Self-Funded'),
            ('bank', 'Bank'),
            ('project_finance', 'Project Finance'),
        ],
        string="Funding Source",
    )
    financial_extract_duration = fields.Selection(
        selection=[
            ('monthly', 'Monthly Billing'),
            ('quarterly', 'Quarterly Billing'),
        ],
        string="Financial Extract Duration",
    )
    payment_cycle = fields.Selection(
        selection=[
            ('30', '30 Days'),
            ('60', '60 Days'),
            ('90', '90 Days'),
            ('180', '180 Days'),
            ('eop', 'End of Project'),
        ],
        string="Payment Cycle",
    )
    advance_payment_percent = fields.Float(string="Advance Payment %")
    payment_terms_type = fields.Selection(
        selection=[
            ('milestone', 'Milestone-based'),
            ('monthly', 'Monthly Progress Billing'),
        ],
        string="Payment Terms",
    )
    recommendation = fields.Text(string="Recommendation")

    def action_payment_request(self):
        self.ensure_one()
        return {
            'name': _('Register Payment'),
            'type': 'ir.actions.act_window',
            'res_model': 'project.payment.request',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_bid_file_id': self.id,
            }
        }

    def action_create_estimation(self):
        for rec in self:
            rec.state = 'estimated'
            if self.env['estimation'].search([('lead_id', '=', rec.lead_id.id)]):
                raise UserError(_('An Estimation already exists for this Lead.'))
            if not self.customer_id:
                raise UserError(_('Please select a Customer before creating an Estimation.'))
            estimation_obj = self.env['estimation']
            estimation_vals = {
                'lead_id': rec.lead_id.id,
                'partner_id': rec.customer_id.id,
                'st_date': rec.start_date,
                'end_date': rec.end_date,
            }
            estimation = estimation_obj.create(estimation_vals)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Estimation',
                'res_model': 'estimation',
                'view_mode': 'form',
                'view_type': 'form',
                'res_id': estimation.id
            }

    def action_open_estimation(self):
        for rec in self:
            est = self.env['estimation'].search([('lead_id', '=', rec.lead_id.id)], limit=1)
            if not est:
                raise UserError(_('No Estimation found for this Tender.'))
            return {
                'name': _('Estimation'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'estimation',
                'res_id': est.id,
                'type': 'ir.actions.act_window',
            }

    def action_open_payments(self):
        return {
            'name': _('Payment'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.bank.statement.line',
            'view_mode': 'list',
            'domain': [('bid_file_id', '=', self.id)],
        }

    @api.depends('start_date', 'end_date')
    def _compute_project_duration(self):
        for rec in self:
            if rec.start_date and rec.end_date:
                delta = relativedelta(
                    rec.end_date, rec.start_date
                )
                rec.project_duration = (
                    f"{delta.years} Years, "
                    f"{delta.months} Months, "
                    f"{delta.days} Days"
                )
            else:
                rec.project_duration = False

    def action_create_initial_guarantee(self):
        return {
            'name': _('Create Initial Bank Guarantee'),
            'type': 'ir.actions.act_window',
            'res_model': 'bank.guarantee',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_guarantee_type': 'initial',
                'default_bid_file_id': self.id,
                'default_project_value': self.bid_estimated_value,
                'default_bank_guarantee_percent': self.bank_guarantee_percent,
                'default_bank_guarantee_value': self.bank_guarantee_value,
                'default_ref': self.name + ' - Initial Bank Guarantee',
            }
        }

    def action_create_final_guarantee(self):
        return {
            'name': _('Create Final Bank Guarantee'),
            'type': 'ir.actions.act_window',
            'res_model': 'bank.guarantee',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_guarantee_type': 'final',
                'default_bid_file_id': self.id,
                'default_project_value': self.bid_estimated_value,
                'default_bank_guarantee_percent': self.final_bank_guarantee_percent,
                'default_bank_guarantee_value': self.final_bank_guarantee_value,
                'default_ref': self.name + ' - Final Bank Guarantee',
            }
        }


class ProjectCustomerDeduction(models.Model):
    _name = 'project.customer.deduction'

    bid_file_id = fields.Many2one('bid.file')
    name = fields.Char()
    product_id = fields.Many2one('product.product')
    deduction_type = fields.Selection([
        ('amount', 'Amount'),
        ('percent', 'Percentage')
    ])
    value = fields.Float()


class ProjectSubcontractDeduction(models.Model):
    _name = 'project.subcontract.deduction'

    bid_file_id = fields.Many2one('bid.file')
    name = fields.Char()
    product_id = fields.Many2one('product.product')
    deduction_type = fields.Selection([
        ('amount', 'Amount'),
        ('percent', 'Percentage')
    ])
    value = fields.Float()


class ProjectCustomerAddition(models.Model):
    _name = 'project.customer.addition'

    bid_file_id = fields.Many2one('bid.file')
    tax_id = fields.Many2one('account.tax')
    amount = fields.Float()


class ProjectSubcontractAddition(models.Model):
    _name = 'project.subcontract.addition'

    bid_file_id = fields.Many2one('bid.file')
    tax_id = fields.Many2one('account.tax')
    amount = fields.Float()
