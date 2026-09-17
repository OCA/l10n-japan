# Copyright 2026 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

# Reference cases for the canonical (katakana) form, shared between the mixin's
# own tests and the res.partner ones, so that the same table is exercised both
# directly against the converter and through create() and write() on a model
# that actually has a table.
KANA_CASES = [
    # (input, expected) -- note
    ("ﾔﾏﾀﾞｼｮｳｼﾞ", "ヤマダショウジ"),  # half-width -> full-width
    ("やまだしょうじ", "ヤマダショウジ"),  # hiragana -> katakana
    ("ｶﾞ", "ガ"),  # half-width voiced pair composes
    ("ｺｰﾋｰ", "コーヒー"),  # long-vowel mark survives
    ("ﾔﾏﾀﾞ ﾀﾛｳ", "ヤマダ タロウ"),  # separation is preserved
    ("ヤマダ　タロウ", "ヤマダ タロウ"),  # IME full-width space (U+3000) is canonical
    ("ヤマダ  タロウ", "ヤマダ タロウ"),  # a repeated separator collapses
    ("　ヤマダ　タロウ ", "ヤマダ タロウ"),  # the edges are trimmed
]
