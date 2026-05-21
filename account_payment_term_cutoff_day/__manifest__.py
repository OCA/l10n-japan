# Copyright 2025 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Account Payment Term Cutoff Day",
    "summary": "支払条件に締日の概念を追加",
    "version": "19.0.1.0.0",
    "depends": ["account"],
    "author": "Quartile, Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "website": "https://github.com/OCA/l10n-japan",
    "category": "Accounting",
    "data": [
        "views/account_payment_term_views.xml",
        "views/account_move_views.xml",
    ],
    "demo": [
        "demo/account_payment_term_demo.xml",
    ],
    "installable": True,
    "maintainers": ["yostashiro", "AungKoKoLin1997"],
}
