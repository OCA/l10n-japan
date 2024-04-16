# Copyright 2024 Quartile Limited
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "JP Partner Corporate Number",
    "version": "16.0.1.0.0",
    "license": "AGPL-3",
    "author": "Quartile Limited, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-japan",
    "depends": ["base", "base_country_state_translatable"],
    "data": [
        "views/res_company_views.xml",
        "views/res_partner_views.xml",
    ],
    "demo": ["demo/demo_ir_config_parameter.xml"],
    "installable": True,
    "application": False,
    "auto_install": False,
}
