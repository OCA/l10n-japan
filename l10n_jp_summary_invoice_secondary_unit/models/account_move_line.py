# Copyright 2026 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    # We want to avoid the use of t-esc to manipulate the sign of the secondary_uom_qty
    # in the report, as it prevents the display adjustments by report_qweb_field_option.
    signed_secondary_uom_qty = fields.Float(
        compute="_compute_signed_secondary_uom_qty",
        digits="Product Unit of Measure",
        help="Technical field used to display the value with the correct sign in "
        "reports.",
    )

    def _compute_signed_secondary_uom_qty(self):
        for line in self:
            sign = -1 if line.move_type in ("out_refund", "in_refund") else 1
            line.signed_secondary_uom_qty = line.secondary_uom_qty * sign
