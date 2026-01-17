# Copyright 2025 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Japan Summary Invoice - Carryover",
    "summary": "Add carryover amount tracking to summary invoices",
    "version": "18.0.1.0.0",
    "category": "Japanese Localization",
    "author": "Quartile, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-japan",
    "license": "AGPL-3",
    "depends": ["l10n_jp_summary_invoice"],
    "data": [
        "reports/report_summary_invoice_templates.xml",
        "views/account_billing_views.xml",
        "views/res_config_settings_views.xml",
        "views/res_partner_views.xml",
    ],
    "development_status": "Alpha",
    "maintainers": ["yostashiro", "aungkokolin1997"],
    "installable": True,
}
