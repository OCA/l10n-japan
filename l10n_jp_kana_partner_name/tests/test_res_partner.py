# Copyright 2026 Quartile (https://www.quartile.co)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo.tests.common import TransactionCase


class TestResPartnerNameKana(TransactionCase):
    """Only what res.partner adds.

    The mixins themselves are covered against a model of their own in
    l10n_jp_kana; repeating that matrix here would test nothing this module
    contributes.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["res.partner"]

    def test_the_mixins_are_wired_in(self):
        partner = self.partner_model.create({"name": "Partner", "name_kana": "ﾔﾏﾀﾞｼｮｳｼﾞ"})
        self.assertEqual(partner.name_kana, "ヤマダショウジ")

    def test_name_search_normalizes_input_and_keeps_core_keys(self):
        """res.partner searches its display name over email and ref as well.

        Our kana condition is ORed into that override, so those keys have to
        keep matching.
        """
        partner = self.partner_model.create(
            {
                "name": "Kana Search Partner",
                "name_kana": "ﾔﾏﾀﾞｼｮｳｼﾞ",
                "email": "kana-search@example.com",
                "ref": "KANA-REF",
            }
        )

        def search_ids(term):
            return {
                record_id
                for record_id, _display_name in self.partner_model.name_search(term)
            }

        for term in ("ヤマダショウジ", "やまだしょうじ", "ﾔﾏﾀﾞｼｮｳｼﾞ"):
            with self.subTest(term=term):
                self.assertIn(partner.id, search_ids(term))
        for term in ("kana-search@example.com", "KANA-REF"):
            with self.subTest(term=term):
                self.assertIn(partner.id, search_ids(term))

    def test_search_view_filters_on_the_normalizing_field(self):
        """A search view compares the term to the column as typed, so filtering
        on name_kana itself would only match a term typed in the stored form.
        """
        arch = self.partner_model.get_view(view_type="search")["arch"]
        self.assertIn("name_kana_search", arch)
        self.assertNotIn('name="name_kana"', arch)
