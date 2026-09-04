from odoo import models, fields, api, _
from odoo.exceptions import UserError


class CrmLeadInherit(models.Model):
    _inherit = 'crm.lead'

    project_type = fields.Selection([
        ('product', 'Product'),
        ('private', 'Private'),
        ('tender', 'Tender'),
    ], string='Project Type', default='product')

    contracting_party = fields.Selection(string="Contracting Party",
                                         selection=[('direct_with_customer', 'Direct with Customer'), (
                                             'direct_with_project_contractor', 'Direct With Project Contractor')])

    contracting_agreement = fields.Selection(string="Contracting Agreement",
                                             selection=[('tender', 'Tender'), ('invitation', 'Invitation')])

    contract_term_type = fields.Selection(string="Contract Term Type",
                                          selection=[('long_term_contract', 'Long Term Contract'),
                                                     ('short_term_contract', 'Short Term Contract')])

    invitation_for_bid_date = fields.Date(string="Invitation For Bid Date")
    tender_booklet_value = fields.Float(string="Tender Booklet Value")
    project_name = fields.Char(string="Project Name")
    project_code = fields.Char(string="Project Code")
    customer_responsible_person_id = fields.Many2one('res.partner', string="Customer's Responsible Person")
    phone = fields.Char(string="Phone")
    mobile = fields.Char(string="Mobile")
    email = fields.Char(string="Email")
    submit_address = fields.Text(string="Submit Address")

    # additional details new group
    english_name = fields.Char(string="English Name")
    project_category = fields.Many2many('crm.project.category', string="Project Category")
    submission_date = fields.Date(string="Submission Date")
    service_category = fields.Selection(string="Service Category",
                                        selection=[('supply_only', 'Supply Only'), ('apply_only', 'Apply Only'),
                                                   ('supply_and_apply', 'Supply and Apply')], default='supply_only')
    project_status = fields.Selection([
        ('tender', 'Tender'),
        ('on_hand', 'On Hand'),
    ], string='Project Status', default='tender')
    required_registration = fields.Boolean(string="Required Registration")
    site_survey_required = fields.Boolean(string="Site Survey Required")

    # end user new tab
    end_user_name = fields.Char(string="End User Name")
    end_user_contact_person = fields.Char(string="Contact Person")
    end_user_phone_number = fields.Char(string="Phone Number")
    end_user_email = fields.Char(string="Email")
    end_user_location = fields.Char(string="Location")

    # consultant new tab
    consultant_firm_name = fields.Char(string="Consultant Firm Name")
    consultant_contact_person = fields.Char(string="Contact Person")
    consultant_phone_number = fields.Char(string="Phone Number")
    consultant_email = fields.Char(string="Email")
    consultant_location = fields.Char(string="Location")

    def action_open_bid_file(self):
        for rec in self:
            bid_file = self.env['bid.file'].search([('lead_id', '=', rec.id)], limit=1)
            if not bid_file:
                raise UserError(_('No bid file found for this Lead.'))
            return {
                'name': _('Bid file'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'bid.file',
                'res_id': bid_file.id,
                'type': 'ir.actions.act_window',
            }

    def action_open_estimation(self):
        for rec in self:
            est = self.env['estimation'].search([('lead_id', '=', rec.id)], limit=1)
            if not est:
                raise UserError(_('No Estimation found for this Lead.'))
            return {
                'name': _('Estimation'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'estimation',
                'res_id': est.id,
                'type': 'ir.actions.act_window',
            }

    def action_create_bid_file(self):
        for rec in self:
            if self.env['bid.file'].search([('lead_id', '=', rec.id)]):
                raise UserError(_('This bid file already exists for this Lead.'))
            if not rec.tender_booklet_value or rec.tender_booklet_value <= 0:
                raise UserError(_('Tender Booklet Value must be greater than zero to create a Bid File.'))
            bid_file_obj = self.env['bid.file']
            bid_file_vals = {
                'lead_id': rec.id,
            }
            bid_file = bid_file_obj.create(bid_file_vals)
            return {
                'name': _('Bid File'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'bid.file',
                'res_id': bid_file.id,
                'type': 'ir.actions.act_window',
            }

    def action_estimation(self):
        for rec in self:
            if self.env['estimation'].search([('lead_id', '=', rec.id)]):
                raise UserError(_('An Estimation already exists for this Lead.'))
            if not self.partner_id:
                raise UserError(_('Please select a Partner before creating an Estimation.'))
            estimation_obj = self.env['estimation']
            estimation_vals = {
                'lead_id': rec.id,
                'partner_id': rec.partner_id.id,
                'st_date': rec.create_date,
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


class CrmProjectCategory(models.Model):
    _name = 'crm.project.category'

    name = fields.Char(string="Project Category Name", required=True)
