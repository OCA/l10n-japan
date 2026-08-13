# Copyright 2025 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Account Billing From Cutoff",
    "summary": "Create billings based on invoice cutoff dates",
    "version": "18.0.1.0.0",
    "depends": [
        "account_billing",
        "account_payment_term_cutoff_day",
        "l10n_jp_summary_invoice",
    ],
    "author": "Quartile, Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "website": "https://github.com/OCA/l10n-japan",
    "category": "Accounting",
    "data": [
        "security/ir.model.access.csv",
        "wizards/account_billing_cutoff.xml",
    ],
    "development_status": "Alpha",
    "maintainers": ["yostashiro", "aungkokolin1997"],
    "installable": True,
}
