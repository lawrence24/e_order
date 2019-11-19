# -*- coding: utf-8 -*-
{
    'name': "eJob Order",
    'summary': "job order",
    'desription': "job order",
    'author': "Joven Lawrence P. Gersaniba",
    'website': "",
    'category': 'Test',
    'version': '1.33',

    'depends':[
        'base','account_accountant', 'web_notify', 'stock',
    ],

    'data': [
        'data/its_province.xml',
        'security/ejob_order_security.xml',
        'security/ir.model.access.csv',
        'wizards/payment_processing.xml',
        'wizards/charge_slip_entry_wizard.xml',
        'views/menu.xml',
        'report/report_menu.xml',
        'views/e_job_order_views.xml',
        'views/jo_sequence.xml',
        'report/ejob_order_report_view.xml',
        'report/ejob_order_slip_view.xml',
        'views/custom_registry_view.xml',
        'views/addresses_conf_view.xml',
        'views/ejob_payment_customer_registry.xml',
        'views/ejob_soa_view.xml',
        'views/custom_hr_view.xml',
    ],

}
