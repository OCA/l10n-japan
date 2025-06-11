# Copyright 2025 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class AccountTaxGroup(models.Model):
    _inherit = "account.tax.group"

    def _get_tax_for_group(self):
        return self.env["account.tax"].search([("tax_group_id", "=", self.id)], limit=1)

    def _get_adjustment_tax(self):
        self.ensure_one()
        adjustment_tax = self.env["account.tax"].search(
            [("rounding_adjustment", "=", True), ("tax_group_id", "=", self.id)],
            limit=1,
        )
        if not adjustment_tax:
            origin_tax = self._get_tax_for_group()
            adjustment_tax = origin_tax.copy(
                {
                    "name": f"Adjustment - {self.name}",
                    "amount_type": "division",
                    "amount": 100.0,
                    "price_include_override": "tax_included",
                    "description": "N/A",
                    "rounding_adjustment": True,
                }
            )
        return adjustment_tax
