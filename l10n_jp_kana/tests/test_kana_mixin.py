# Copyright 2026 Quartile (https://www.quartile.co)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from unittest.mock import patch

from odoo.exceptions import UserError

from ..models.kana_mixin import KANA_FORMAT_PARAM
from .common import KANA_CASES, KanaCase


class TestKanaMixin(KanaCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mixin = cls.env["kana.mixin"]

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
        self._set_format(False, model=self.mixin._name)
        self.assertEqual(self.mixin._normalize_name_kana("ヤマダ"), "やまだ")

    def test_invalid_format_parameter_is_refused(self):
        with self.assertRaises(UserError):
            self._set_format("romaji")
        # Also on an existing parameter, which goes through write().
        self._set_format("hiragana")
        with self.assertRaises(UserError):
            self._set_format("romaji")
        with self.assertRaises(UserError):
            self._set_format("romaji", model="res.partner")

    def test_a_rename_is_validated_against_the_new_key(self):
        param = self.param.create({"key": "l10n_jp_kana.formt", "value": "romaji"})
        with self.assertRaises(UserError):
            param.key = f"{KANA_FORMAT_PARAM}.res.partner"
        # Leaving the kana keys behind is not ours to refuse.
        kana_param = self.param.create(
            {"key": f"{KANA_FORMAT_PARAM}.res.partner", "value": "hiragana"}
        )
        kana_param.write({"key": "l10n_jp_kana.note", "value": "romaji"})
        self.assertEqual(kana_param.value, "romaji")

    def test_unsupported_format_is_not_converted(self):
        with patch.object(
            self.env.registry["kana.mixin"],
            "_get_kana_format",
            return_value="romaji",
        ):
            with self.assertRaises(UserError):
                self.mixin._normalize_name_kana("ﾔﾏﾀﾞ")

    def test_the_two_callers_treat_a_blank_differently(self):
        for value in ("   ", "　", "", False):
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
