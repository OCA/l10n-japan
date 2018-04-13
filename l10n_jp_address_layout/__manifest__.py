# -*- coding: utf-8 -*-
# Copyright 2018 Quartile Limited
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
{
    'name': 'Japan Address Layout',
    'version': '11.0.1.1.0',
    'depends': [
        'base',
    ],
    'author': 'Quartile Limited, '
              'Odoo Community Association (OCA)',
    'license': "LGPL-3",
    'website': 'https://odoo-community.org/',
    'category': 'Extra Tools',
    'description': """
This module provides Japan address input field layout in views
The module also extends the default partner title model, allowing the title
to be shown in most printed reports.
    """,
    'data': [
        'views/assets.xml',
        'views/res_partner_title_views.xml',
        'views/res_partner_views.xml',
        'views/templates.xml',
        'data/res_country_data.xml',
        'data/res_partner_title_data.xml',
    ],
    'installable': True,
}
