# -*- coding: utf-8 -*-
# Copyright 2018 Quartile Limited
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
{
    'name': 'Website Sale Search (Japanese characters compatible)',
    'version': '11.0.1.0.0',
    'depends': [
        'website_sale',
    ],
    'author': 'Quartile Limited, '
              'Odoo Community Association (OCA)',
    'license': "LGPL-3",
    'website': 'https://odoo-community.org/',
    'category': 'eCommerce',
    'description': """
Allow the search field in eCommerce matches other form of the Japanese
language, e.g. Kanji / Hinagana / Katakana.
Convert all the ascii characters into half-spaced for search.
    """,
    'data': [
    ],
    'external_dependencies': {'python': ['jaconv']},
    'installable': True,
}
