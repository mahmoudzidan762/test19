{
    'name': 'Tender Management for Construction',
    'version': '1.0',
    'summary': 'Digital Projecta for Construction Management Spicially in Tendering Phase',
    'description': """ """,
    "license": "LGPL-3",
    'author': 'Dgprojx',
    'depends': ['base', 'mail', 'hr', 'dg_construction', 'accountant'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/bid_file_view.xml',
        'views/crm_lead_inherit.xml',
        'wizards/project_payment_request.xml',
        'wizards/bank_guarantee.xml',
    ],

    'demo': [],
    'installable': True,
    'application': True,
}
