# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

ACTION_TYPE_SELECTION = [
    ('act_window', 'Window Action'),
    ('server', 'Server Action'),
    ('client', 'Client Action'),
]


class SimplifyAccessAction(models.Model):
    """Action Access configuration line (Phase 6).

    Restricts one specific action, referenced via a concrete Many2one
    matching `action_type` (act_window_id / server_action_id /
    client_action_id) rather than one generic, unsafely-typed reference
    field - this keeps each reference natively validated by the ORM
    (correct model, correct ondelete cascade) rather than relying on
    manual model-name + id bookkeeping.
    """
    _name = 'simplify.access.action'
    _description = 'Access Management Action Rule'
    _order = 'name'

    access_rule_id = fields.Many2one(
        comodel_name='simplify.access.rule',
        string='Access Rule',
        required=True,
        ondelete='cascade',
        index=True,
    )

    action_type = fields.Selection(
        selection=ACTION_TYPE_SELECTION,
        string='Action Type',
        required=True,
        default='act_window',
    )

    act_window_id = fields.Many2one(
        comodel_name='ir.actions.act_window',
        string='Window Action',
        ondelete='cascade',
    )
    server_action_id = fields.Many2one(
        comodel_name='ir.actions.server',
        string='Server Action',
        ondelete='cascade',
    )
    client_action_id = fields.Many2one(
        comodel_name='ir.actions.client',
        string='Client Action',
        ondelete='cascade',
    )

    name = fields.Char(
        string='Name',
        compute='_compute_name',
        store=True,
        help='Informational, derived from the selected action.',
    )

    active = fields.Boolean(string='Active', default=True)

    @api.depends('action_type', 'act_window_id.name', 'server_action_id.name',
                 'client_action_id.name')
    def _compute_name(self):
        for line in self:
            if line.action_type == 'act_window':
                line.name = line.act_window_id.name or ''
            elif line.action_type == 'server':
                line.name = line.server_action_id.name or ''
            elif line.action_type == 'client':
                line.name = line.client_action_id.name or ''
            else:
                line.name = ''

    @api.constrains('action_type', 'act_window_id', 'server_action_id', 'client_action_id')
    def _check_exactly_one_action_reference(self):
        for line in self:
            refs = {
                'act_window': line.act_window_id,
                'server': line.server_action_id,
                'client': line.client_action_id,
            }
            expected_ref = refs.get(line.action_type)
            if not expected_ref:
                raise ValidationError(_(
                    'Select the %(type)s matching the chosen Action Type.',
                    type=dict(ACTION_TYPE_SELECTION).get(line.action_type, line.action_type),
                ))
            other_refs = [v for k, v in refs.items() if k != line.action_type]
            if any(other_refs):
                raise ValidationError(_(
                    'Only one action reference (Window/Server/Client) '
                    'may be set, matching the selected Action Type.'
                ))

    _sql_constraints = [
        (
            'unique_act_window_per_rule',
            'unique(access_rule_id, act_window_id)',
            'This window action is already configured in this access '
            'rule.',
        ),
        (
            'unique_server_action_per_rule',
            'unique(access_rule_id, server_action_id)',
            'This server action is already configured in this access '
            'rule.',
        ),
        (
            'unique_client_action_per_rule',
            'unique(access_rule_id, client_action_id)',
            'This client action is already configured in this access '
            'rule.',
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
