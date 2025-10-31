# Copyright 2025 Quartile (https://www.quartile.co)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo.tools.sql import column_exists, table_exists


def migrate(cr, version):
    if not version:
        return
    # Only run if BOTH the old column and table still exist after the core migration.
    if not (
        column_exists(cr, "res_partner", "title")
        and table_exists(cr, "res_partner_title")
    ):
        return
    cr.execute(
        """
        UPDATE res_partner AS p
           SET honorific_title = t.name,
               honorific_title_position = COALESCE(t.display_position, 'after')
          FROM res_partner_title AS t
         WHERE p.title = t.id
        """
    )
