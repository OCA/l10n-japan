# Copyright 2022 Quartile Limited
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
{
    "name": "Japan Address Layout",
    "version": "15.0.1.0.0",
    "depends": ["web"],
    "author": "Quartile Limited, " "Odoo Community Association (OCA)",
    "license": "LGPL-3",
    "website": "https://github.com/OCA/l10n-japan",
    "category": "Localization",
    "data": [
        "views/res_partner_views.xml",
        "data/res_country_data.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "l10n_jp_address_layout/static/src/scss/form_view.scss",
        ],
    },
    "installable": True,
}
