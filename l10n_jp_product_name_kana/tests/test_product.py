# Copyright 2026 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests.common import TransactionCase


class TestProductNameKana(TransactionCase):
    def test_template_and_variant_name_search(self):
        template = self.env["product.template"].create(
            {"name": "Kana Product", "name_kana": "ｵﾌｨｽﾁｪｱ"}
        )
        self.assertEqual(template.name_kana, "オフィスチェア")
        template_ids = {
            record_id
            for record_id, _display_name in self.env["product.template"].name_search(
                "おふぃすちぇあ"
            )
        }
        self.assertIn(template.id, template_ids)
        product_ids = {
            record_id
            for record_id, _display_name in self.env["product.product"].name_search(
                "ｵﾌｨｽﾁｪｱ"
            )
        }
        self.assertIn(template.product_variant_id.id, product_ids)

    def test_search_view_field_normalizes_the_term(self):
        """Both product search views filter on name_kana_search.

        product.product has no reading of its own -- it reaches the field
        through the product_tmpl_id delegation, so the search has to resolve
        across it.
        """
        template = self.env["product.template"].create(
            {"name": "Kana Product", "name_kana": "ｵﾌｨｽﾁｪｱ"}
        )
        for model, record in (
            (self.env["product.template"], template),
            (self.env["product.product"], template.product_variant_id),
        ):
            for term in ("オフィスチェア", "おふぃすちぇあ", "ｵﾌｨｽﾁｪｱ"):
                with self.subTest(model=model._name, term=term):
                    found = model.search([("name_kana_search", "ilike", term)])
                    self.assertIn(record.id, found.ids)

    def test_variant_write_normalizes_the_reading(self):
        """A reading set on the variant is normalized without a reread.

        name_kana reaches product.product through the product_tmpl_id
        delegation, so the value has to be normalized here too, not only by the
        mixin on product.template.
        """
        template = self.env["product.template"].create({"name": "Kana Product"})
        variant = template.product_variant_id
        variant.write({"name_kana": "ｵﾌｨｽﾁｪｱ"})
        self.assertEqual(variant.name_kana, "オフィスチェア")
        self.assertEqual(template.name_kana, "オフィスチェア")

    def test_variant_create_normalizes_the_reading(self):
        variant = self.env["product.product"].create(
            {"name": "Kana Product", "name_kana": "ｵﾌｨｽﾁｪｱ"}
        )
        self.assertEqual(variant.name_kana, "オフィスチェア")
