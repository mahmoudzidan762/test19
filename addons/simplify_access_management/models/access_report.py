# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SimplifyAccessReport(models.Model):
    """Report Access configuration line (Phase 6)."""
    _name = 'simplify.access.report'
    _description = 'Access Management Report Rule'
    _order = 'model_name, report_name'

    access_rule_id = fields.Many2one(
        comodel_name='simplify.access.rule',
        string='Access Rule',
        required=True,
        ondelete='cascade',
        index=True,
    )

    report_id = fields.Many2one(
        comodel_name='ir.actions.report',
        string='Report',
        required=True,
        ondelete='cascade',
    )
    model_name = fields.Char(
        related='report_id.model',
        string='Technical Model Name',
        store=True,
        readonly=True,
    )
    report_name = fields.Char(
        related='report_id.report_name',
        string='Technical Report Name',
        store=True,
        readonly=True,
        help='The report\'s technical qweb template reference (e.g. '
             '"module.report_template_id").',
    )

    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        (
            'unique_report_per_rule',
            'unique(access_rule_id, report_id)',
            'This report is already configured in this access rule.',
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env['simplify.access.policy'].clear_caches()
        return records

    def write(self, vals):
        result = super().write(vals)
        self.env['simplify.access.policy'].clear_caches()
        return result

    def unlink(self):
        result = super().unlink()
        self.env['simplify.access.policy'].clear_caches()
        return result
