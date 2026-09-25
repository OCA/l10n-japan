# Copyright 2026 Quartile (https://www.quartile.co)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

{
    "name": "Japanese Kana",
    "summary": "Normalized kana readings for any model, and their format setting",
    "version": "19.0.1.0.0",
    "category": "Localization/Japan",
    "author": "Quartile, Odoo Community Association (OCA)",
    "maintainers": ["AungKoKoLin1997"],
    "website": "https://github.com/OCA/l10n-japan",
    "license": "LGPL-3",
    "depends": ["base_setup"],
    "data": [
        "views/res_config_settings_views.xml",
    ],
    "external_dependencies": {"python": ["jaconv"]},
    "installable": True,
}
