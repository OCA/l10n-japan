# Copyright 2026 Quartile (https://www.quartile.co)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo.tests.common import TransactionCase, new_test_user

from odoo.addons.l10n_jp_kana.models.kana_mixin import KANA_FORMAT_PARAM


class TestHrEmployeeNameKana(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee_model = cls.env["hr.employee"]
        cls.public_model = cls.env["hr.employee.public"]
        cls.param = cls.env["ir.config_parameter"].sudo()

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
        employee = self.employee_model.create(
            {"name": "Kana Employee", "name_kana": "ﾔﾏﾀﾞ ﾀﾛｳ"}
        )
        for model in (self.employee_model, self.public_model):
            for term in ("ヤマダ タロウ", "やまだ たろう", "ﾔﾏﾀﾞ ﾀﾛｳ"):
                with self.subTest(model=model._name, term=term):
                    found = model.search([("name_kana_search", "ilike", term)])
                    self.assertIn(employee.id, found.ids)

    def test_public_employee_follows_the_employee_format(self):
        self.param.set_param(KANA_FORMAT_PARAM, "full_width_katakana")
        self.param.set_param(f"{KANA_FORMAT_PARAM}.hr.employee", "hiragana")
        employee = self.employee_model.create(
            {"name": "Hiragana Employee", "name_kana": "ﾔﾏﾀﾞ ﾀﾛｳ"}
        )
        self.assertEqual(employee.name_kana, "やまだ たろう")
        self.assertIn(employee.id, self._search_public_ids("ヤマダ タロウ"))

    def test_user_without_hr_access_finds_employee_by_kana(self):
        employee = self.employee_model.create(
            {"name": "Kana Employee", "name_kana": "ﾔﾏﾀﾞ ﾀﾛｳ"}
        )
        user = new_test_user(self.env, login="kana_no_hr", groups="base.group_user")
        model = self.employee_model.with_user(user)
        found_ids = [employee_id for employee_id, _name in model.name_search("やまだ")]
        self.assertIn(employee.id, found_ids)
        self.assertIn(
            employee.id, model.search([("name_kana_search", "ilike", "ﾔﾏﾀﾞ")]).ids
        )
        self.assertEqual(model.browse(employee.id).name_kana, "ヤマダ タロウ")
