# Copyright 2024-2025 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Japan Summary Invoice",
    "version": "18.0.1.0.0",
    "category": "Japanese Localization",
    "author": "Quartile, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-japan",
    "license": "AGPL-3",
    "depends": ["account_billing", "report_alternative_layout"],
    "data": [
        "reports/report_summary_invoice_templates.xml",
        "reports/summary_invoice_reports.xml",
        "views/account_billing_views.xml",
        "views/account_move_views.xml",
        "views/account_tax_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "development_status": "Alpha",
    "installable": True,
}
