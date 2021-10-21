# Copyright 2018-2019 Quartile Limited
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    'name': 'Japan Country States',
    'version': '12.0.1.0.0',
    'depends': [
        'base_country_state_translatable',
    ],
    'author': 'Enzantrades inc, '
              'Quartile Limited, '
              'Odoo Community Association (OCA)',
    'license': "AGPL-3",
    'website': 'https://github.com/OCA/l10n-japan',
    'category': 'Localization',
    'description': """
This module updates Japanese prefecture data with translation.
    """,
    'data': [
        'data/res_country_state.xml',
    ],
    'installable': True,
}
