# Copyright 2026 Quartile (https://www.quartile.co)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo.orm.model_classes import add_to_registry
from odoo.tests import Form

from .common import KANA_CASES, KanaCase


class TestNameKanaMixin(KanaCase):
    """The mixins against a concrete model, on a fake one of our own.

    A model-specific test belongs in the module that adds the mixins to its
    model; what is checked here holds for any of them.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Imported here, not at module level: a registry load outside the
        # tests would otherwise pick the fake models up.
        from .fake_models import KanaTestAlias, KanaTestRecord

        defs = (KanaTestRecord, KanaTestAlias)
        names = [model_def._name for model_def in defs]
        for model_def in defs:
            add_to_registry(cls.registry, model_def)
        cls.registry._setup_models__(cls.env.cr, names)
        cls.registry.init_models(cls.env.cr, names, {"models_to_check": True})
        # __delitem__ also drops the model from the mixins' _inherit_children;
        # the tables go with the test transaction.
        for name in names:
            cls.addClassCleanup(cls.registry.__delitem__, name)
        cls.model = cls.env[KanaTestRecord._name]
        cls.alias_model = cls.env[KanaTestAlias._name]

    def test_normalized_on_create(self):
        records = self.model.create(
            [
                {"name": f"Record {index}", "name_kana": value}
                for index, (value, _expected) in enumerate(KANA_CASES)
            ]
        )
        self.assertEqual(
            records.mapped("name_kana"), [expected for _value, expected in KANA_CASES]
        )

    def test_normalized_on_write(self):
        record = self.model.create({"name": "Record"})
        for value, expected in KANA_CASES:
            with self.subTest(value=value):
                record.name_kana = value
                self.assertEqual(record.name_kana, expected)

    def test_a_field_declared_on_the_model_is_normalized_too(self):
        """kana.mixin can be taken on its own, with the consumer declaring the
        Char fields it wants normalized (see USAGE).
        """
        self.assertEqual(self.alias_model._get_kana_fields(), ["alias_kana"])
        record = self.alias_model.create({"name": "Record", "alias_kana": "ﾔﾏﾀﾞ"})
        self.assertEqual(record.alias_kana, "ヤマダ")
        record.alias_kana = "すずき"
        self.assertEqual(record.alias_kana, "スズキ")
        record.alias_kana = "　"  # the IME's U+3000
        self.assertFalse(record.alias_kana)

    def test_neither_mixin_derives_from_the_other(self):
        """A model can end up with both, from two modules that do not know of
        each other, and a derivation would then break its MRO.
        """
        kana, name_kana = self.registry["kana.mixin"], self.registry["name.kana.mixin"]
        self.assertFalse(issubclass(name_kana, kana))
        self.assertFalse(issubclass(kana, name_kana))
        for bases in ((kana, name_kana), (name_kana, kana)):
            with self.subTest(first=bases[0]._name):
                type(
                    "kana.mro.probe",
                    bases,
                    {"__module__": __name__, "_register": False},
                )

    def test_a_consumer_carries_kana_mixin_itself(self):
        """Not just the behaviour: a module extending kana.mixin has to reach
        the model, and it only does if kana.mixin is in the model's own MRO.
        """
        for model in (self.model, self.alias_model):
            with self.subTest(model=model._name):
                self.assertTrue(
                    issubclass(self.registry[model._name], self.registry["kana.mixin"])
                )

    def test_form_shows_the_normalized_reading_before_save(self):
        with Form(self.model) as form:
            form.name = "Record"
            form.name_kana = "ﾔﾏﾀﾞ ﾀﾛｳ"
            self.assertEqual(form.name_kana, "ヤマダ タロウ")
            form.name_kana = "　"  # the IME's U+3000
            self.assertFalse(form.name_kana)
            form.name_kana = "やまだ　たろう"
        self.assertEqual(form.record.name_kana, "ヤマダ タロウ")

    def test_blank_value_is_stored_as_no_reading(self):
        record = self.model.create({"name": "Record", "name_kana": False})
        self.assertFalse(record.name_kana)
        for value in ("   ", "　"):  # U+0020 and the IME's U+3000
            with self.subTest(value=repr(value)):
                record.name_kana = value
                self.assertFalse(record.name_kana)

    def test_model_setting_overrides_global_setting(self):
        self._set_format("hiragana")
        self._set_format("half_width_katakana", model=self.model._name)
        record = self.model.create({"name": "Record", "name_kana": "やまだしょうじ"})
        self.assertEqual(record.name_kana, "ﾔﾏﾀﾞｼｮｳｼﾞ")

    def test_model_setting_falls_back_to_global_setting(self):
        self._set_format("hiragana")
        record = self.model.create({"name": "Record", "name_kana": "ﾔﾏﾀﾞｼｮｳｼﾞ"})
        self.assertEqual(record.name_kana, "やまだしょうじ")

    def test_format_change_leaves_stored_readings_as_they_are(self):
        """Stored readings keep their format until saved again (see ROADMAP)."""
        self._set_format("full_width_katakana")
        record = self.model.create({"name": "Record", "name_kana": "やまだしょうじ"})
        self.assertEqual(record.name_kana, "ヤマダショウジ")
        settings = self.env["res.config.settings"].create({})
        settings.kana_format = "hiragana"
        settings.set_values()
        self.assertEqual(record.name_kana, "ヤマダショウジ")
        record.name_kana = "ヤマダショウジ"
        self.assertEqual(record.name_kana, "やまだしょうじ")

    def test_display_name_collection_operators_normalize_every_member(self):
        """``=`` becomes ``in`` with an OrderedSet; each member is normalized."""
        record = self.model.create({"name": "Record", "name_kana": "ﾔﾏﾀﾞｼｮｳｼﾞ"})
        term = "やまだしょうじ"
        for operator, value in [("=", term), ("in", [term]), ("in", (term,))]:
            with self.subTest(operator=operator, value=type(value).__name__):
                found = self.model.search([("display_name", operator, value)])
                self.assertIn(record, found)

    def test_display_name_negative_operator_excludes_the_kana_match(self):
        """A negative operator ANDs the kana condition; OR would match everything."""
        matching = self.model.create({"name": "Alpha", "name_kana": "ﾔﾏﾀﾞ"})
        other = self.model.create({"name": "Beta", "name_kana": "スズキ"})
        found = self.model.search([("display_name", "not ilike", "やまだ")])
        self.assertNotIn(matching, found)
        self.assertIn(other, found)

    def test_whitespace_does_not_partition_the_column(self):
        """An IME's U+3000 and an import's U+0020 must store the same reading."""
        ime = self.model.create({"name": "IME", "name_kana": "ヤマダ　タロウ"})
        imported = self.model.create({"name": "Imported", "name_kana": "ﾔﾏﾀﾞ ﾀﾛｳ"})
        padded = self.model.create({"name": "Padded", "name_kana": " ヤマダ  タロウ　"})
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
                found = {record_id for record_id, _name in self.model.name_search(term)}
                self.assertIn(ime.id, found)
                self.assertIn(imported.id, found)
                self.assertIn(padded.id, found)

    def test_search_field_normalizes_the_term(self):
        """A search view compares the term to the column as typed, so it filters
        on name_kana_search rather than on name_kana itself.
        """
        record = self.model.create({"name": "Record", "name_kana": "ﾔﾏﾀﾞｼｮｳｼﾞ"})
        other = self.model.create({"name": "Other", "name_kana": "スズキ"})
        # An IME leaves a trailing space after committing a conversion.
        for term in (
            "ヤマダショウジ",
            "やまだしょうじ",
            "ﾔﾏﾀﾞｼｮｳｼﾞ",
            "ヤマダ",
            "ヤマダ　",
        ):
            with self.subTest(term=term):
                found = self.model.search([("name_kana_search", "ilike", term)])
                self.assertIn(record, found)
                self.assertNotIn(other, found)

    def test_search_field_is_a_readonly_mirror(self):
        """Readonly keeps it out of the import wizard; a write must not reach it."""
        record = self.model.create({"name": "Record", "name_kana": "ﾔﾏﾀﾞ"})
        self.assertEqual(record.name_kana_search, record.name_kana)
        description = self.model.fields_get(["name_kana_search"])
        self.assertTrue(description["name_kana_search"]["readonly"])
        record.write({"name_kana_search": "ｽｽﾞｷ"})
        record.invalidate_recordset()
        self.assertEqual(record.name_kana, "ヤマダ")
        self.assertEqual(record.name_kana_search, "ヤマダ")
