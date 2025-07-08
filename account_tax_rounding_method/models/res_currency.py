# Copyright 2025 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models, tools


class Currency(models.Model):
    _inherit = "res.currency"

    def round(self, amount):
        self.ensure_one()
        tax_rounding_method = self.env.context.get("tax_rounding_method")
        if tax_rounding_method:
            return tools.float_round(
                amount,
                precision_rounding=self.rounding,
                rounding_method=tax_rounding_method,
            )
        return super().round(amount)
