{
    'name': 'Estimation Management for Construction',
    'version': '1.0',
    'summary': 'Digital Projecta for Construction Management Spicially in Estimation Phase',
    'description': """ """,
    "license": "LGPL-3",
    'author': 'Dgprojx',
    'depends': ['base', 'mail', 'product', 'crm', 'sale_management', 'dg_construction'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/estimation_view.xml',
        'views/cost_details_view.xml',
        'views/product_template_inherit.xml',
        'views/menus.xml',
    ],

    'demo': [],
    'installable': True,
    'application': True,
}
