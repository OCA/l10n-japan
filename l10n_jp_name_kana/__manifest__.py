# Copyright 2026 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Japanese Kana Name",
    "summary": "Add a normalized kana name to contacts, and a mixin to reuse it",
    "version": "19.0.1.0.0",
    "category": "Localization/Japan",
    "author": "Quartile, Odoo Community Association (OCA)",
    "maintainers": ["AungKoKoLin1997"],
    "website": "https://github.com/OCA/l10n-japan",
    "license": "AGPL-3",
    "depends": ["base_setup"],
    "data": [
        "views/res_partner_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "external_dependencies": {"python": ["jaconv"]},
    "installable": True,
}
