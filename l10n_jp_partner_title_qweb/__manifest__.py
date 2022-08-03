# Copyright 2018-2019 Quartile Limited
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
{
    'name': 'Japan Partner Title QWeb',
    'version': '12.0.1.0.0',
    'depends': [
        'base',
    ],
    'author': 'Quartile Limited, '
              'Odoo Community Association (OCA)',
    'license': "LGPL-3",
    'website': 'https://github.com/OCA/l10n-japan',
    'category': 'Localization',
    'description': """
The module extends the default partner title model to allow the title
to be shown in most printed reports.
    """,
    'data': [
        'views/res_partner_title_views.xml',
        'views/res_partner_views.xml',
        'report/templates.xml',
        'data/res_partner_title_data.xml',
    ],
    'installable': True,
}
