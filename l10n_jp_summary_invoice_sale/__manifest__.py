# Copyright 2025 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Japan Summary Invoice Sale",
    "summary": "Show sales order number and reference in summary invoice",
    "version": "16.0.1.0.0",
    "category": "Japanese Localization",
    "author": "Quartile, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-japan",
    "license": "AGPL-3",
    "depends": ["sale", "l10n_jp_summary_invoice"],
    "data": [
        "reports/report_summary_invoice_templates.xml",
        "views/res_config_settings_views.xml",
    ],
    "development_status": "Alpha",
    "maintainers": ["yostashiro", "aungkokolin1997"],
    "installable": True,
}
