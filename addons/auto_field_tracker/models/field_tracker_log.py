# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class FieldTrackerLog(models.Model):
    """
    Permanent audit log for every field change tracked by Auto Field Tracker.
    Each row = one field changed on one record at one point in time.
    """
    _name = 'field.tracker.log'
    _description = 'Field Tracker Change Log'
    _order = 'write_date desc'
    _rec_name = 'field_label'

    # ─── Source Config ──────────────────────────────────────────────
    config_id = fields.Many2one(
        'field.tracker.config',
        string='Tracker Config',
        ondelete='set null',
        index=True,
    )

    # ─── What changed ───────────────────────────────────────────────
    model_name = fields.Char(
        string='Model',
        required=True,
        index=True,
        help='Technical name of the model (e.g. sale.order)',
    )
    model_label = fields.Char(
        string='Model Label',
        help='Human-readable model name',
    )
    record_id = fields.Integer(
        string='Record ID',
        required=True,
        index=True,
    )
    record_name = fields.Char(
        string='Record Name',
        help='display_name of the record at time of change',
    )
    field_name = fields.Char(
        string='Field (Technical)',
        required=True,
    )
    field_label = fields.Char(
        string='Field Label',
        help='Human-readable field name',
    )
    field_type = fields.Char(
        string='Field Type',
        help='Odoo field type: char, selection, many2one, float, etc.',
    )

    # ─── Old / New values ───────────────────────────────────────────
    old_value = fields.Char(string='Old Value')
    new_value = fields.Char(string='New Value')
    old_value_id = fields.Integer(
        string='Old Value ID',
        help='For relational fields: ID of the old linked record',
    )
    new_value_id = fields.Integer(
        string='New Value ID',
        help='For relational fields: ID of the new linked record',
    )

    # ─── Who / When ─────────────────────────────────────────────────
    changed_by = fields.Many2one(
        'res.users',
        string='Changed By',
        index=True,
        ondelete='set null',
    )
    changed_by_name = fields.Char(
        string='Changed By (Name)',
        help='Stored name in case user is later deleted',
    )
    change_type = fields.Selection([
        ('create', 'Created'),
        ('write',  'Updated'),
        ('unlink', 'Deleted'),
    ], string='Change Type', default='write', index=True)

    # ─── Computed / Display ─────────────────────────────────────────
    summary = fields.Char(
        string='Summary',
        compute='_compute_summary',
        store=True,
    )

    @api.depends('field_label', 'old_value', 'new_value', 'change_type')
    def _compute_summary(self):
        for rec in self:
            if rec.change_type == 'create':
                rec.summary = _(
                    '%(field)s set to "%(new)s"'
                ) % {'field': rec.field_label or rec.field_name, 'new': rec.new_value or '—'}
            elif rec.change_type == 'unlink':
                rec.summary = _('Record deleted')
            else:
                rec.summary = _(
                    '%(field)s: "%(old)s" → "%(new)s"'
                ) % {
                    'field': rec.field_label or rec.field_name,
                    'old': rec.old_value or '—',
                    'new': rec.new_value or '—',
                }

    def action_open_record(self):
        """Navigate to the original changed record."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self.model_name,
            'res_id': self.record_id,
            'view_mode': 'form',
            'target': 'current',
        }
