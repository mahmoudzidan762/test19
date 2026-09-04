# -*- coding: utf-8 -*-
{
    'name': 'Auto Field Tracker',
    'version': '19.0.1.0.0',
    'category': 'Technical',
    'summary': 'Field Tracker | Audit Trail | Audit Log | Field Change History | Chatter Log | Record Tracking | Data Tracking | Change History | Field Change Log | Field Monitoring | Auto Track | Field Update Tracker',
    'description': """
Auto Field Tracker
==================

Auto Field Tracker by Odoovix lets administrators configure audit tracking for chatter-enabled Odoo models without changing source code.

Main capabilities:
- Track create, write, and delete operations per model.
- Track all eligible fields or selected fields only.
- Log old and new values in the record chatter.
- Store searchable audit history in a dedicated log model.
- Track selected One2many child-line changes on the parent record.
- Skip transient, binary, internal mail, and technical models automatically.
    """,
    'author': 'Odoovix',
   'website': 'https://apps.odoo.com/apps/modules/browse?author=Odoovix',
    'support': 'support@odoovix.com',
    'depends': [
        'base',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/field_tracker_config_views.xml',
        'views/field_tracker_log_views.xml',
        'views/res_config_settings_views.xml',
        'data/field_tracker_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'auto_field_tracker/static/description/field_tracker.css',
        ],
    },
    'installable': True,
    'auto_install': False,
     'images': ['static/description/banner.png'],
    'application': True,
    'license': 'LGPL-3',
}
