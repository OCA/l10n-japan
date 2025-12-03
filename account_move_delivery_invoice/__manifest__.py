# Copyright 2025 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Account Move Delivery Invoice",
    "version": "18.0.1.0.0",
    "depends": ["account"],
    "author": "Quartile, Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "website": "https://github.com/OCA/l10n-japan",
    "category": "Accounting",
    "data": [
        "views/account_move_views.xml",
        "views/res_config_settings_views.xml",
        "report/report_delivery_note_template.xml",
        "report/report_delivery_note.xml",
        "report/report_invoice_document.xml",
    ],
    "maintainers": ["yostashiro", "aungkokolin1997"],
    "installable": True,
}
