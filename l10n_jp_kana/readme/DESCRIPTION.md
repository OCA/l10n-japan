Provides the abstract models that give a phonetic reading (カナ / ふりがな) to
a model -- of its name, or of any other field -- and the setting that chooses
the kana format readings are stored in.

A reading is stored in a canonical form, so the same pronunciation matches
however it was typed: kana take the configured format, full-width ASCII and
digits fold to half-width (ＡＢＣショウジ is stored as ABCショウジ), and spacing
collapses to single half-width spaces. A search term goes through the same
normalization before it is compared.

ヵ and ヶ become カ in every format, as they stand for 箇. In half-width
katakana, kana with no half-width form fold to the nearest one that has: ヮ to
ﾜ, ヰ and ヱ to ｲ and ｴ, ヷ-ヺ to ｳﾞ with a small vowel, and the small katakana
for Ainu to their full-size forms.

This module adds no field to any model of its own; the readings live in the
modules that apply the mixins to a model.
