# Copyright 2026 Quartile (https://www.quartile.co)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo.tests.common import TransactionCase

from ..models.kana_mixin import KANA_FORMAT_PARAM

# (input, expected) for the default format.
KANA_CASES = [
    ("ﾔﾏﾀﾞｼｮｳｼﾞ", "ヤマダショウジ"),  # half-width -> full-width
    ("やまだしょうじ", "ヤマダショウジ"),  # hiragana -> katakana
    ("ｶﾞ", "ガ"),  # half-width voiced pair composes
    ("ｺｰﾋｰ", "コーヒー"),  # long-vowel mark survives
    ("ﾔﾏﾀﾞ ﾀﾛｳ", "ヤマダ タロウ"),  # separation is preserved
    ("ヤマダ　タロウ", "ヤマダ タロウ"),  # full-width space (U+3000) folds to a space
    ("ヤマダ  タロウ", "ヤマダ タロウ"),  # a repeated separator collapses
    ("　ヤマダ　タロウ ", "ヤマダ タロウ"),  # the edges are trimmed
    ("ＡＢＣショウジ", "ABCショウジ"),  # full-width ASCII folds to half-width
    ("ABCショウジ", "ABCショウジ"),  # and half-width ASCII is already canonical
    ("３Ｍジャパン", "3Mジャパン"),  # the same for digits
]


class KanaCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.param = cls.env["ir.config_parameter"].sudo()

    def _set_format(self, value, model=None):
        key = f"{KANA_FORMAT_PARAM}.{model}" if model else KANA_FORMAT_PARAM
        self.param.set_param(key, value)
