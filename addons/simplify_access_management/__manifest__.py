{
    'name': 'Simplify Access Management',
    'version': '19.0.1.0.0',
    'category': 'Tools',
    'summary': 'Centralized, user-specific access configuration for Odoo',
    'description': """
Simplify Access Management
===========================

Phase 1 - Foundation & Configuration
-------------------------------------
This phase introduces the Access Management data model and configuration
screens only. No access restriction is enforced yet - that is the
responsibility of later development phases, which will build on top of the
``simplify.access.rule`` model and the ``simplify.access.policy`` helper
introduced here.

Provided in this phase:

* An "Access Management / Manager" security group.
* The ``simplify.access.rule`` configuration model (user- and
  company-specific rules).
* A policy helper foundation (``simplify.access.policy``) exposing:

  - ``_get_applicable_rules(user, company)``
  - ``_is_access_manager(user)``
  - ``_is_bypass_user(user)``

* Configuration menus and views (list, form, search).
""",
    'author': 'Your Company',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
        'mail',
        'base_import',
    ],
    'data': [
        'security/access_groups.xml',
        'security/ir.model.access.csv',
        'views/access_view_element_picker_views.xml',
        'views/access_rule_views.xml',
        'views/access_menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'simplify_access_management/static/src/js/simplify_hide_import.js',
            'simplify_access_management/static/src/js/simplify_list_action_menu.js',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
