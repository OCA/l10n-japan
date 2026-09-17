# Copyright 2026 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Japan Summary Invoice Untaxed Unrounded",
    "summary": "Show unrounded subtotals and untaxed amounts on the summary "
    "invoice report when currency rounding hides decimals",
    "version": "18.0.1.0.0",
    "category": "Japanese Localization",
    "author": "Quartile, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-japan",
    "license": "AGPL-3",
    "depends": [
        "l10n_jp_summary_invoice",
        "account_invoice_report_untaxed_unrounded",
    ],
    "data": [
        "reports/report_summary_invoice_templates.xml",
    ],
    "maintainers": ["yostashiro", "aungkokolin1997"],
    "auto_install": True,
    "installable": True,
}
