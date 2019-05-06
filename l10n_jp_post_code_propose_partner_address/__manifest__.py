# Copyright 2019 Quartile Limited
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
{
    'name': 'Post Code (JP) Propose Partner Address',
    'version': '11.0.1.0.0',
    'author': 'Quartile Limited, '
              'Odoo Community Association (OCA)',
    'license': "LGPL-3",
    'website': 'https://odoo-community.org/',
    'category': 'Localization',
    'depends': [
        'l10n_jp_country_state',
    ],
    'external_dependencies': {
        'python': ['jaconv'],
    },
    'data': [
    ],
    'installable': True,
}
