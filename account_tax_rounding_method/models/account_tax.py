# Copyright 2025 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models


class AccountTax(models.Model):
    _inherit = "account.tax"

    @api.model
    def _get_tax_rounding_method(
        self,
        company,
        partner=None,
    ):
        if partner and partner.tax_rounding_method:
            return partner.tax_rounding_method
        return company.tax_rounding_method

    @api.model
    def _round_tax_details_tax_amounts(self, base_lines, company, mode="mixed"):
        tax_rounding_method = self.env.context.get("tax_rounding_method")
        if tax_rounding_method:
            company = company.with_context(tax_rounding_method=tax_rounding_method)
            for base_line in base_lines:
                currency = base_line.get("currency_id")
                if currency:
                    base_line["currency_id"] = currency.with_context(
                        tax_rounding_method=tax_rounding_method
                    )
        return super()._round_tax_details_tax_amounts(base_lines, company, mode=mode)

    @api.model
    def _round_base_lines_tax_details(self, base_lines, company, tax_lines=None):
        def is_all_price_included(bl):
            taxes = bl.get("tax_ids") or self.env["account.tax"]
            return bool(taxes) and all(t.price_include for t in taxes)

        # Skip setting the context when every tax is price-included.
        if all(is_all_price_included(bl) for bl in base_lines):
            return super()._round_base_lines_tax_details(
                base_lines, company, tax_lines=tax_lines
            )
        partner = (
            base_lines and base_lines[0].get("partner_id") or self.env["res.partner"]
        )
        method = self._get_tax_rounding_method(company, partner)
        self = self.with_context(tax_rounding_method=method)
        return super()._round_base_lines_tax_details(
            base_lines, company, tax_lines=tax_lines
        )
