# Copyright 2026 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from ..models.name_kana_mixin import KANA_FORMAT_PARAM
from .common import KANA_CASES


class TestNameKanaMixin(TransactionCase):
    """The mixin has no table, so only the converter and the resolution of the
    format setting are covered here. The ORM paths live in the consumer modules.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mixin = cls.env["name.kana.mixin"]
        cls.param = cls.env["ir.config_parameter"].sudo()

    def setUp(self):
        super().setUp()
        # ir.config_parameter is ormcached and that cache is only cleared
        # between test classes, so a rolled-back parameter would leak here.
        self.env.registry.clear_cache("stable")

    def _set_format(self, value, model=None):
        key = f"{KANA_FORMAT_PARAM}.{model}" if model else KANA_FORMAT_PARAM
        self.param.set_param(key, value)

    def test_full_width_katakana(self):
        self._set_format("full_width_katakana")
        for value, expected in KANA_CASES:
            with self.subTest(value=value):
                self.assertEqual(self.mixin._normalize_name_kana(value), expected)

    def test_half_width_katakana(self):
        self._set_format("half_width_katakana")
        self.assertEqual(self.mixin._normalize_name_kana("ﾔﾏﾀﾞｼｮｳｼﾞ"), "ﾔﾏﾀﾞｼｮｳｼﾞ")
        self.assertEqual(self.mixin._normalize_name_kana("やまだしょうじ"), "ﾔﾏﾀﾞｼｮｳｼﾞ")
        self.assertEqual(self.mixin._normalize_name_kana("ヤマダショウジ"), "ﾔﾏﾀﾞｼｮｳｼﾞ")

    def test_hiragana(self):
        self._set_format("hiragana")
        self.assertEqual(self.mixin._normalize_name_kana("ﾔﾏﾀﾞｼｮｳｼﾞ"), "やまだしょうじ")
        self.assertEqual(
            self.mixin._normalize_name_kana("ヤマダショウジ"), "やまだしょうじ"
        )

    def test_full_width_katakana_is_the_default(self):
        self.assertEqual(
            self.mixin._normalize_name_kana("やまだしょうじ"), "ヤマダショウジ"
        )

    def test_model_setting_wins_over_global_setting(self):
        self._set_format("hiragana")
        self._set_format("half_width_katakana", model=self.mixin._name)
        self.assertEqual(self.mixin._normalize_name_kana("やまだ"), "ﾔﾏﾀﾞ")
        # Clearing it falls back to the global setting.
        self._set_format(False, model=self.mixin._name)
        self.assertEqual(self.mixin._normalize_name_kana("ヤマダ"), "やまだ")

    def test_invalid_format_parameter_is_refused(self):
        """A typo is caught when the parameter is written, not on the next save."""
        with self.assertRaises(UserError):
            self._set_format("romaji")
        with self.assertRaises(UserError):
            self._set_format("romaji", model="res.partner")

    def test_unsupported_format_is_not_converted(self):
        """Defence in depth: the parameter could be set outside the ORM."""
        with patch.object(
            self.env.registry["name.kana.mixin"],
            "_get_kana_format",
            return_value="romaji",
        ):
            with self.assertRaises(UserError):
                self.mixin._normalize_name_kana("ﾔﾏﾀﾞ")

    def test_blank_values_are_returned_unchanged(self):
        self.assertFalse(self.mixin._normalize_name_kana(False))
        self.assertEqual(self.mixin._normalize_name_kana(""), "")
        self.assertEqual(self.mixin._normalize_name_kana("   "), "   ")

    def test_the_two_callers_treat_a_blank_differently(self):
        """A blank is no reading on the way in, but stays as typed on the way out.

        Storing "   " would leave a truthy value that counts as a reading
        everywhere; normalizing a blank *term* to False would instead turn it
        into a search for an empty reading.
        """
        for value in ("   ", "　", ""):
            with self.subTest(value=repr(value)):
                self.assertFalse(self.mixin._normalize_name_kana_write_value(value))
                self.assertEqual(
                    self.mixin._normalize_name_kana_search_value(value), value
                )

    def test_settings_field_stores_the_parameter(self):
        settings = self.env["res.config.settings"].create({})
        settings.kana_format = "hiragana"
        settings.set_values()
        self.assertEqual(self.param.get_param(KANA_FORMAT_PARAM), "hiragana")
