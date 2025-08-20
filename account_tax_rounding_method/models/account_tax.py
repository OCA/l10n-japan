# Copyright 2025 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models


class AccountTax(models.Model):
    _inherit = "account.tax"

    @api.model
    def _get_tax_rounding_method(self, partners=None):
        if partners and len(partners) == 1 and partners[0].tax_rounding_method:
            return partners[0].tax_rounding_method
        return self.env.company.tax_rounding_method

    @api.model
    def _compute_taxes(
        self,
        base_lines,
        tax_lines=None,
        handle_price_include=True,
        include_caba_tags=False,
    ):
        # We assume all base_lines share the same partner,
        # so we use the partner from the first line
        partner = (
            base_lines[0].get("partner") if base_lines else self.env["res.partner"]
        )
        tax_rounding_method = self._get_tax_rounding_method(partner)
        self = self.with_context(tax_rounding_method=tax_rounding_method)
        return super()._compute_taxes(
            base_lines,
            tax_lines=tax_lines,
            handle_price_include=handle_price_include,
            include_caba_tags=include_caba_tags,
        )

    @api.model
    def _aggregate_taxes(
        self,
        to_process,
        filter_tax_values_to_apply=None,
        grouping_key_generator=None,
        distribute_total_on_line=True,
    ):
        # Clear the tax_rounding_method context if only inclusive taxes are present
        # in to_process, to avoid affecting the rounding behavior and to follow
        # the standard behavior.
        all_price_include = all(
            all(tax.get("price_include") for tax in tax_values_list)
            for _, _, tax_values_list in to_process
        )
        if all_price_include:
            self = self.with_context(tax_rounding_method=None)
        return super()._aggregate_taxes(
            to_process,
            filter_tax_values_to_apply=filter_tax_values_to_apply,
            grouping_key_generator=grouping_key_generator,
            distribute_total_on_line=distribute_total_on_line,
        )

    @api.model
    def _prepare_tax_totals(
        self, base_lines, currency, tax_lines=None, is_company_currency_requested=False
    ):
        # We assume all base_lines share the same partner,
        # so we use the partner from the first line
        partner = (
            base_lines[0].get("partner") if base_lines else self.env["res.partner"]
        )
        tax_rounding_method = self._get_tax_rounding_method(partner)
        self = self.with_context(tax_rounding_method=tax_rounding_method)
        return super()._prepare_tax_totals(
            base_lines,
            currency,
            tax_lines=tax_lines,
            is_company_currency_requested=is_company_currency_requested,
        )
