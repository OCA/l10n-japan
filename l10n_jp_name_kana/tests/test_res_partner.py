# Copyright 2026 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests.common import TransactionCase

from ..models.name_kana_mixin import KANA_FORMAT_PARAM
from .common import KANA_CASES


class TestResPartnerNameKana(TransactionCase):
    """The mixin has no table of its own, so its write path is covered here,
    on a real consumer model.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["res.partner"]
        cls.param = cls.env["ir.config_parameter"].sudo()

    def setUp(self):
        super().setUp()
        # ir.config_parameter is ormcached and that cache is only cleared
        # between test classes, so a rolled-back parameter would leak here.
        self.env.registry.clear_cache("stable")

    def _set_format(self, value, model=None):
        key = f"{KANA_FORMAT_PARAM}.{model}" if model else KANA_FORMAT_PARAM
        self.param.set_param(key, value)

    def test_normalized_on_create(self):
        partners = self.partner_model.create(
            [
                {"name": f"Partner {index}", "name_kana": value}
                for index, (value, _expected) in enumerate(KANA_CASES)
            ]
        )
        self.assertEqual(
            partners.mapped("name_kana"), [expected for _value, expected in KANA_CASES]
        )

    def test_normalized_on_write(self):
        partner = self.partner_model.create({"name": "Partner"})
        for value, expected in KANA_CASES:
            with self.subTest(value=value):
                partner.name_kana = value
                self.assertEqual(partner.name_kana, expected)

    def test_blank_value_is_stored_as_no_reading(self):
        """A whitespace-only reading is truthy, so it would count as a reading."""
        partner = self.partner_model.create({"name": "Partner", "name_kana": False})
        self.assertFalse(partner.name_kana)
        for value in ("   ", "　"):  # U+0020 and the IME's U+3000
            with self.subTest(value=repr(value)):
                partner.name_kana = value
                self.assertFalse(partner.name_kana)

    def test_model_setting_overrides_global_setting(self):
        self._set_format("hiragana")
        self._set_format("half_width_katakana", model="res.partner")
        partner = self.partner_model.create(
            {"name": "Partner", "name_kana": "やまだしょうじ"}
        )
        self.assertEqual(partner.name_kana, "ﾔﾏﾀﾞｼｮｳｼﾞ")

    def test_model_setting_falls_back_to_global_setting(self):
        self._set_format("hiragana")
        partner = self.partner_model.create({"name": "Partner", "name_kana": "ﾔﾏﾀﾞｼｮｳｼﾞ"})
        self.assertEqual(partner.name_kana, "やまだしょうじ")

    def test_format_change_leaves_stored_readings_as_they_are(self):
        """A format change applies to what is saved after it, not before it.

        Rewriting the rows already stored costs one UPDATE per row -- readings
        are close to unique, so there is nothing to group them by -- which on a
        table of any size outlasts the request that changes the setting and
        rolls it back, leaving the format unchangeable. See the ROADMAP.
        """
        self._set_format("full_width_katakana")
        partner = self.partner_model.create(
            {"name": "Partner", "name_kana": "やまだしょうじ"}
        )
        self.assertEqual(partner.name_kana, "ヤマダショウジ")
        settings = self.env["res.config.settings"].create({})
        settings.kana_format = "hiragana"
        settings.set_values()
        self.assertEqual(partner.name_kana, "ヤマダショウジ")
        # Saving the reading again is what moves it to the new format.
        partner.name_kana = "ヤマダショウジ"
        self.assertEqual(partner.name_kana, "やまだしょうじ")

    def test_display_name_collection_operators_normalize_every_member(self):
        """The ORM rewrites `=` into `in` carrying an OrderedSet.

        So this is not an exotic hand-written domain: every equality search on
        display_name takes the collection branch. Normalizing only list and
        tuple leaves the term as typed, and the kana condition matches nothing.
        """
        partner = self.partner_model.create({"name": "Partner", "name_kana": "ﾔﾏﾀﾞｼｮｳｼﾞ"})
        term = "やまだしょうじ"
        for operator, value in [("=", term), ("in", [term]), ("in", (term,))]:
            with self.subTest(operator=operator, value=type(value).__name__):
                found = self.partner_model.search([("display_name", operator, value)])
                self.assertIn(partner, found)

    def test_whitespace_does_not_partition_the_column(self):
        """A Japanese IME emits U+3000 between name parts; imports emit U+0020.

        jaconv touches neither, nor a doubled or trailing space, so without
        canonicalizing the separator the column holds one spelling per way of
        typing the gap -- and each is only found by the term that repeats it.
        """
        ime = self.partner_model.create({"name": "IME", "name_kana": "ヤマダ　タロウ"})
        imported = self.partner_model.create(
            {"name": "Imported", "name_kana": "ﾔﾏﾀﾞ ﾀﾛｳ"}
        )
        padded = self.partner_model.create(
            {"name": "Padded", "name_kana": " ヤマダ  タロウ　"}
        )
        self.assertEqual(ime.name_kana, imported.name_kana)
        self.assertEqual(ime.name_kana, padded.name_kana)
        for term in (
            "ヤマダ　タロウ",
            "ヤマダ タロウ",
            "ﾔﾏﾀﾞ ﾀﾛｳ",
            "やまだ　たろう",
            "ヤマダ  タロウ",
            "ヤマダ　タロウ ",
        ):
            with self.subTest(term=term):
                found = {
                    record_id
                    for record_id, _name in self.partner_model.name_search(term)
                }
                self.assertIn(ime.id, found)
                self.assertIn(imported.id, found)
                self.assertIn(padded.id, found)

    def test_search_view_field_normalizes_the_term(self):
        """The search view filters on name_kana_search, not on name_kana.

        A search view compares the term to the column as typed, so a filter on
        name_kana itself finds nothing whenever the two are in different kana
        forms -- while the contact lookup, which normalizes, finds the record.
        """
        partner = self.partner_model.create({"name": "Partner", "name_kana": "ﾔﾏﾀﾞｼｮｳｼﾞ"})
        other = self.partner_model.create({"name": "Other", "name_kana": "スズキ"})
        # The trailing space is what an IME leaves behind after committing a
        # conversion, so a term carrying one has to find the record too.
        for term in (
            "ヤマダショウジ",
            "やまだしょうじ",
            "ﾔﾏﾀﾞｼｮｳｼﾞ",
            "ヤマダ",
            "ヤマダ　",
        ):
            with self.subTest(term=term):
                found = self.partner_model.search([("name_kana_search", "ilike", term)])
                self.assertIn(partner, found)
                self.assertNotIn(other, found)

    def test_search_view_field_is_a_readonly_mirror(self):
        """It must not look like an input the reading can be entered through.

        A bare search hook with no compute reads as False and is reported
        writable, which is enough for the import wizard to offer it as a
        column -- one the ORM then accepts and stores nowhere.
        """
        partner = self.partner_model.create({"name": "Partner", "name_kana": "ﾔﾏﾀﾞ"})
        self.assertEqual(partner.name_kana_search, partner.name_kana)
        description = self.partner_model.fields_get(["name_kana_search"])
        self.assertTrue(description["name_kana_search"]["readonly"])
        # Readonly is what keeps it out of the import field list; the ORM
        # itself never refuses a write to a non-stored field, so check that one
        # cannot reach the stored reading.
        partner.write({"name_kana_search": "ｽｽﾞｷ"})
        partner.invalidate_recordset()
        self.assertEqual(partner.name_kana, "ヤマダ")
        self.assertEqual(partner.name_kana_search, "ヤマダ")

    def test_display_name_negative_operator_excludes_the_kana_match(self):
        """A negative operator has to AND the kana condition, not OR it.

        OR-ing it would match everything: a record whose reading matches still
        satisfies the negative condition on the other search keys, so the union
        would be the whole table.
        """
        matching = self.partner_model.create({"name": "Alpha", "name_kana": "ﾔﾏﾀﾞ"})
        other = self.partner_model.create({"name": "Beta", "name_kana": "スズキ"})
        found = self.partner_model.search([("display_name", "not ilike", "やまだ")])
        self.assertNotIn(matching, found)
        self.assertIn(other, found)

    def test_name_search_normalizes_input_and_keeps_core_keys(self):
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

        # The reading is found however the term itself is typed.
        for term in ("ヤマダショウジ", "やまだしょうじ", "ﾔﾏﾀﾞｼｮｳｼﾞ"):
            with self.subTest(term=term):
                self.assertIn(partner.id, search_ids(term))
        # The core search keys still work.
        for term in ("kana-search@example.com", "KANA-REF"):
            with self.subTest(term=term):
                self.assertIn(partner.id, search_ids(term))
