# Copyright 2026 Quartile (https://www.quartile.co)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import api, models
from odoo.fields import Domain


class ProductProduct(models.Model):
    _name = "product.product"
    _inherit = ["product.product", "kana.mixin"]

    @api.onchange("name_kana")
    def _onchange_name_kana(self):
        # name.kana.mixin declares this on the template; the variant needs its
        # own, the field reaching it through the product_tmpl_id delegation.
        self._normalize_kana_field("name_kana")

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        template_model = self.env["product.template"]
        normalized_name = template_model._normalize_name_kana_search_value(name)
        kana_domain = Domain("product_tmpl_id.name_kana", operator, normalized_name)
        domain = Domain(domain or Domain.TRUE)
        if operator in Domain.NEGATIVE_OPERATORS:
            return super().name_search(name, domain & kana_domain, operator, limit)
        results = super().name_search(name, domain, operator, limit)
        remaining = limit and max(limit - len(results), 0)
        if limit and not remaining:
            return results
        matched_ids = [record_id for record_id, _display_name in results]
        kana_products = self.search_fetch(
            domain & Domain("id", "not in", matched_ids) & kana_domain,
            ["display_name"],
            limit=remaining,
        )
        return [
            *results,
            *((product.id, product.display_name) for product in kana_products.sudo()),
        ]

    @api.model
    def _search_display_name(self, operator, value):
        domain = super()._search_display_name(operator, value)
        template_model = self.env["product.template"]
        kana_domain = Domain(
            "product_tmpl_id.name_kana",
            operator,
            template_model._normalize_name_kana_search_value(value),
        )
        if operator in Domain.NEGATIVE_OPERATORS:
            return Domain.AND([domain, kana_domain])
        return Domain.OR([domain, kana_domain])
