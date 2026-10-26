# -*- coding: utf-8 -*-
{
    'name': 'Institutional Inventory & Procurement Management',
    'version': '19.0.1.0.0',
    'category': 'Inventory/Procurement',
    'summary': 'Manage institutional supply requisitions, personnel holdings and consumption logs, multi-level approvals, Store Incharge audit trails, IT asset lifecycle custody logs, component composition/decomposition, departmental annual quotas, combined annual requisitions, and non-negative stock governance for Odoo Community Edition (BUTEX).',
    'author': 'Nascenia / Antigravity',
    'website': 'https://www.example.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'product',
        'stock',
        'purchase',
        'hr',
    ],
    'data': [
        # Security
        'security/security_groups.xml',
        'security/security_rules.xml',
        'security/ir.model.access.csv',

        # Data & Sequences
        'data/sequence_data.xml',
        'data/mail_templates.xml',

        # Top-level Menus (Loaded first so parent menu IDs exist for child items)
        'views/menus.xml',

        # Demo & Master Data (Loaded automatically in data)
        'demo/demo_users.xml',
        'demo/demo_departments.xml',
        'demo/demo_employees.xml',
        'demo/demo_products.xml',
        'demo/demo_quotas.xml',
        'demo/demo_assets.xml',
        'demo/demo_requisitions.xml',

        # Views
        'views/product_views.xml',
        'views/department_quota_views.xml',
        'views/asset_views.xml',
        'views/requisition_views.xml',
        'views/pipeline_matrix_views.xml',
        'views/hr_employee_views.xml',
        'views/reporting_views.xml',

        # Reports
        'reports/report_actions.xml',
        'reports/report_requisition_slip.xml',
        'reports/report_asset_registry.xml',
        'reports/report_low_stock.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
    'auto_install': False,
}
