# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SimplifyAccessRule(models.Model):
    """Access Management Rule.

    Phase 1 note
    ------------
    This model is the master configuration record for the Simplify Access
    Management engine. In this phase it is a pure configuration container:
    creating, editing, archiving or deleting a rule has NO effect on what
    any user can actually do in the system yet. Enforcement is implemented
    in later development phases, which will read these records through the
    ``simplify.access.policy`` helper.

    A rule is considered "applicable" to a given user/company (once
    enforcement is implemented) when:
      * active is True, AND
      * the current user is present in user_ids, AND
      * either apply_all_companies is True, OR the current company is
        present in company_ids.
    """
    _name = 'simplify.access.rule'
    _description = 'Access Management Rule'
    _order = 'sequence, name, id'

    name = fields.Char(
        string='Name',
        required=True,
        help='Descriptive name for this access rule (e.g. "Sales Team - '
             'Restricted Access").',
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Inactive rules are ignored by the access engine and are '
             'kept for reference/archival purposes.',
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Determines the display and evaluation order of the rule.',
    )

    user_ids = fields.Many2many(
        comodel_name='res.users',
        relation='simplify_access_rule_user_rel',
        column1='rule_id',
        column2='user_id',
        string='Users',
        help='Users this rule applies to. Rules are always user-specific.',
    )

    company_ids = fields.Many2many(
        comodel_name='res.company',
        relation='simplify_access_rule_company_rel',
        column1='rule_id',
        column2='company_id',
        string='Companies',
        help='Companies this rule applies to. Ignored when '
             '"Apply All Companies" is enabled.',
    )
    apply_all_companies = fields.Boolean(
        string='Apply All Companies',
        default=False,
        help='If enabled, this rule applies regardless of the currently '
             'active company and the "Companies" field below is ignored.',
    )

    notes = fields.Text(
        string='Notes',
        help='Free-form internal notes about the purpose of this rule.',
    )

    model_ids = fields.One2many(
        comodel_name='simplify.access.model',
        inverse_name='access_rule_id',
        string='Model Access',
        help='Per-model create/write/delete restrictions enforced for '
             'the users targeted by this rule.',
    )

    menu_ids = fields.One2many(
        comodel_name='simplify.access.menu',
        inverse_name='access_rule_id',
        string='Menus',
        help='Menus hidden from navigation for the users targeted by '
             'this rule. UI/navigation visibility only - see '
             'simplify.access.menu for details.',
    )

    field_ids = fields.One2many(
        comodel_name='simplify.access.field',
        inverse_name='access_rule_id',
        string='Fields',
        help='Field-level restrictions (invisible, read only, required, '
             'remove external link, hide from export) enforced for the '
             'users targeted by this rule.',
    )

    domain_ids = fields.One2many(
        comodel_name='simplify.access.domain',
        inverse_name='access_rule_id',
        string='Domain Access',
        help='Record-level (domain-based) restrictions enforced for the '
             'users targeted by this rule, resolved dynamically per '
             'request - see simplify.access.domain.',
    )

    button_ids = fields.One2many(
        comodel_name='simplify.access.button',
        inverse_name='access_rule_id',
        string='Hidden Buttons',
        help='Buttons hidden for the users targeted by this rule.',
    )
    tab_ids = fields.One2many(
        comodel_name='simplify.access.tab',
        inverse_name='access_rule_id',
        string='Hidden Tabs',
        help='Notebook tabs/pages hidden for the users targeted by '
             'this rule.',
    )
    view_ids = fields.One2many(
        comodel_name='simplify.access.view',
        inverse_name='access_rule_id',
        string='Hidden Views',
        help='Specific views or view types restricted for the users '
             'targeted by this rule.',
    )
    action_ids = fields.One2many(
        comodel_name='simplify.access.action',
        inverse_name='access_rule_id',
        string='Hidden Actions',
        help='Window/Server/Client actions restricted for the users '
             'targeted by this rule.',
    )
    report_ids = fields.One2many(
        comodel_name='simplify.access.report',
        inverse_name='access_rule_id',
        string='Hidden Reports',
        help='Reports restricted for the users targeted by this rule.',
    )

    # ------------------------------------------------------------------
    # Phase 7 - Global Access
    # ------------------------------------------------------------------
    global_readonly = fields.Boolean(
        string='Global Read Only',
        default=False,
        help='Prevents the users targeted by this rule from creating, '
             'modifying or deleting persistent business records, while '
             'keeping normal wizard/dialog operations available.',
    )
    hide_import = fields.Boolean(
        string='Hide Import',
        default=False,
        help='Removes the standard Import action and denies direct '
             'import requests for the users targeted by this rule.',
    )
    hide_export = fields.Boolean(
        string='Hide Export',
        default=False,
        help='Removes the standard Export action entirely and denies '
             'direct export requests, regardless of Phase 4 '
             'field-specific export settings. This is a global '
             'restriction - it always wins over any single unrestricted '
             'field.',
    )
    hide_archive = fields.Boolean(
        string='Hide Archive',
        default=False,
        help='Removes the Archive action and denies direct '
             'user-originated archive attempts (writing active=False) '
             'for the users targeted by this rule. Internal/system '
             'writes are never affected.',
    )
    hide_unarchive = fields.Boolean(
        string='Hide Unarchive',
        default=False,
        help='Same as Hide Archive, for restoring (active=True) '
             'archived records.',
    )
    hide_duplicate = fields.Boolean(
        string='Hide Duplicate',
        default=False,
        help='Removes the Duplicate action and denies direct copy() '
             'requests for the users targeted by this rule.',
    )

    disable_login = fields.Boolean(
        string='Disable Login',
        default=False,
        help='Prevents the users targeted by this rule from '
             'authenticating. Does NOT delete, archive, or change the '
             'password of the user account - purely a Simplify Access '
             'restriction, reversible by disabling this option. Does '
             'not affect an already-active session - see the module '
             'notes for details.',
    )
    disable_developer_mode = fields.Boolean(
        string='Disable Developer Mode',
        default=False,
        help='Hides Developer Mode UI/controls for the users targeted '
             'by this rule. KNOWN LIMITATION: this hides UI signals '
             'only - it cannot prevent a technically capable user from '
             'still activating debug mode via a manually-crafted URL, '
             'since that is controlled by Odoo\'s own HTTP/session '
             'layer, which this module does not modify.',
    )

    restrict_module_install = fields.Boolean(
        string='Restrict Module Install',
        default=False,
        help='Blocks the users targeted by this rule from installing '
             'modules, enforced server-side on ir.module.module.',
    )
    restrict_module_upgrade = fields.Boolean(
        string='Restrict Module Upgrade',
        default=False,
        help='Blocks the users targeted by this rule from upgrading '
             'modules, enforced server-side on ir.module.module.',
    )
    restrict_module_uninstall = fields.Boolean(
        string='Restrict Module Uninstall',
        default=False,
        help='Blocks the users targeted by this rule from uninstalling '
             'modules, enforced server-side on ir.module.module. '
             'SUPERUSER is never restricted.',
    )

    # ------------------------------------------------------------------
    # Phase 7 - Chatter
    # ------------------------------------------------------------------
    hide_chatter = fields.Boolean(
        string='Hide Chatter',
        default=False,
        help='Hides the entire Chatter panel (messages, log notes, '
             'activities) for the users targeted by this rule. '
             'Independent from the more specific options below - if '
             'this is enabled, the options below have no additional '
             'effect since the whole panel is already hidden.',
    )
    disable_send_message = fields.Boolean(
        string='Disable Send Message',
        default=False,
        help='Existing chatter messages remain readable, but the users '
             'targeted by this rule cannot post new regular messages '
             '(Send Message), enforced server-side. Independent from '
             'Disable Log Note.',
    )
    disable_log_note = fields.Boolean(
        string='Disable Log Note',
        default=False,
        help='Existing chatter messages remain readable, but the users '
             'targeted by this rule cannot post Log Notes, enforced '
             'server-side. Independent from Disable Send Message.',
    )
    disable_activities = fields.Boolean(
        string='Disable Activities',
        default=False,
        help='Prevents the users targeted by this rule from creating '
             'new activities, enforced server-side. Does not affect '
             'activities already scheduled or system/automation-'
             'generated activities.',
    )

    company_count = fields.Integer(
        string='Company Count',
        compute='_compute_company_count',
        help='Technical/informational field: number of companies '
             'explicitly selected on this rule.',
    )

    @api.depends('company_ids')
    def _compute_company_count(self):
        for rule in self:
            rule.company_count = len(rule.company_ids)

    @api.constrains('company_ids', 'apply_all_companies')
    def _check_companies_consistency(self):
        """Light data-quality check only - this is NOT access enforcement.

        A rule that targets no company at all (apply_all_companies is
        False and company_ids is empty) can never become applicable once
        enforcement is implemented, so we warn the administrator early
        instead of letting them save a rule that can never take effect.
        """
        for rule in self:
            if not rule.apply_all_companies and not rule.company_ids:
                raise ValidationError(_(
                    'Access Rule "%(name)s": please select at least one '
                    'company, or enable "Apply All Companies".',
                    name=rule.name,
                ))

    def _compute_display_name(self):
        # NOTE: name_get() is deprecated since Odoo 17; display_name must be
        # computed via this method in Odoo 19.
        for rule in self:
            name = rule.name or ''
            if not rule.active:
                name = _('%(name)s (Archived)', name=name)
            rule.display_name = name

    # ------------------------------------------------------------------
    # Phase 3/5 - policy cache invalidation
    # ------------------------------------------------------------------
    # A rule's active state, user_ids, company_ids or apply_all_companies
    # all affect which menus are hidden for whom (Phase 3) and which
    # domain restrictions apply to whom (Phase 5, dynamic - see
    # models/access_enforcement.py and
    # simplify.access.policy.get_domain_policy()), so any change here
    # must invalidate the Simplify policy cache. Only THIS module's own
    # cache is cleared (see simplify.access.policy.clear_caches()), never
    # any other Odoo cache. No native security records are generated or
    # modified by this module anywhere - domain enforcement is purely
    # dynamic, computed fresh per request.
    #
    # NOTE: same Odoo 19 create() signature assumption as documented in
    # models/access_enforcement.py - please verify against your local
    # source; a mismatch will fail loudly on module upgrade, not silently.
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

    # ------------------------------------------------------------------
    # Phase 6 UX improvement - discover buttons/tabs instead of typing
    # ------------------------------------------------------------------
    def action_open_button_picker(self):
        """Open the discovery wizard so the administrator can pick
        buttons to hide from the real, final architecture of a chosen
        view, instead of typing technical XML names from memory.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Discover Buttons to Hide'),
            'res_model': 'simplify.access.view.element.picker',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_access_rule_id': self.id,
                'default_mode': 'button',
            },
        }

    def action_open_tab_picker(self):
        """Same as action_open_button_picker(), for notebook tabs."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Discover Tabs to Hide'),
            'res_model': 'simplify.access.view.element.picker',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_access_rule_id': self.id,
                'default_mode': 'tab',
            },
        }
