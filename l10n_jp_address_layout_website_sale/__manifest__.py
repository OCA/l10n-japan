# Copyright 2019 Quartile Limited
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
{
    'name': 'Japan Address Layout in E-commerce and website',
    'version': '12.0.1.0.0',
    'author': 'Quartile Limited, '
              'Odoo Community Association (OCA)',
    'license': "LGPL-3",
    'website': 'https://github.com/OCA/l10n-japan',
    'category': 'Localization',
    'description': """
This module provides the Japan address input field layout in E-commerce.
    """,
    'summary': "",
    'depends': [
        'website_sale',
    ],
    'data': [
        'views/templates.xml',
    ],
    'installable': True,
}
