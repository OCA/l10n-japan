Select the kana format under *Settings > General Settings > Japanese Kana*. Full-width katakana is the default; half-width katakana and hiragana are
the alternatives.

A single model can depart from that, for the case where personal furigana is
kept in hiragana while contacts and products stay in katakana. This is rare, so
it has no setting of its own: add a system parameter under
*Settings > Technical > System Parameters* whose key is the model name appended
to the global one, and whose value is one of `full_width_katakana`,
`half_width_katakana` or `hiragana`.

| Key | Applies to |
|---|---|
| `l10n_jp_kana.format` | every model with a reading |
| `l10n_jp_kana.format.res.partner` | contacts |
| `l10n_jp_kana.format.hr.employee` | employees |
| `l10n_jp_kana.format.product.template` | products and their variants |

An empty or absent per-model key means the model follows the global format.

Changing a format affects only the readings saved afterwards -- see Known
Issues.
