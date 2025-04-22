# Copyright 2025 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


def migrate(cr, version):
    cr.execute("""
        UPDATE account_payment_term_line
        SET has_cutoff_day = TRUE
        WHERE cutoff_day BETWEEN 1 AND 30
    """)
