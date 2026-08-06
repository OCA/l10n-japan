# Copyright 2026 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests.common import TransactionCase

from odoo.addons.l10n_jp_name_kana.models.name_kana_mixin import KANA_FORMAT_PARAM


class TestHrEmployeeNameKana(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee_model = cls.env["hr.employee"]
        cls.public_model = cls.env["hr.employee.public"]
        cls.param = cls.env["ir.config_parameter"].sudo()

    def setUp(self):
        super().setUp()
        # ir.config_parameter is ormcached and that cache is only cleared
        # between test classes, so a rolled-back parameter would leak here.
        self.env.registry.clear_cache("stable")

    def _search_public_ids(self, term):
        return {
            employee_id
            for employee_id, _display_name in self.public_model.name_search(term)
        }

    def test_public_employee_exposes_kana_and_searches_it(self):
        employee = self.employee_model.create(
            {"name": "Kana Employee", "name_kana": "ﾔﾏﾀﾞ ﾀﾛｳ"}
        )
        self.assertEqual(employee.name_kana, "ヤマダ タロウ")
        self.assertEqual(
            self.public_model.browse(employee.id).name_kana, "ヤマダ タロウ"
        )
        self.assertIn(employee.id, self._search_public_ids("やまだ たろう"))

    def test_search_view_field_normalizes_the_term(self):
        """Both employee search views filter on name_kana_search.

        A search view compares the term to the column as typed, so a filter on
        name_kana itself would only match a term typed in the stored form.
        """
        employee = self.employee_model.create(
            {"name": "Kana Employee", "name_kana": "ﾔﾏﾀﾞ ﾀﾛｳ"}
        )
        for model in (self.employee_model, self.public_model):
            for term in ("ヤマダ タロウ", "やまだ たろう", "ﾔﾏﾀﾞ ﾀﾛｳ"):
                with self.subTest(model=model._name, term=term):
                    found = model.search([("name_kana_search", "ilike", term)])
                    self.assertIn(employee.id, found.ids)

    def test_public_employee_follows_the_employee_format(self):
        """The SQL view stores nothing, so it must not resolve a format of its own.

        With a setting of its own it would fall back to the global one here and
        normalize the search term to katakana, matching nothing.
        """
        self.param.set_param(KANA_FORMAT_PARAM, "full_width_katakana")
        self.param.set_param(f"{KANA_FORMAT_PARAM}.hr.employee", "hiragana")
        employee = self.employee_model.create(
            {"name": "Hiragana Employee", "name_kana": "ﾔﾏﾀﾞ ﾀﾛｳ"}
        )
        self.assertEqual(employee.name_kana, "やまだ たろう")
        self.assertIn(employee.id, self._search_public_ids("ヤマダ タロウ"))
