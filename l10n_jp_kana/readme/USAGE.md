Install the module that carries the reading to the model you need:

- `l10n_jp_kana_partner_name` -- contacts
- `l10n_jp_kana_product_name` -- products
- `l10n_jp_kana_hr_employee_name` -- employees

To give another model a reading of its name, inherit `kana.mixin` and
`name.kana.mixin` alongside the model and add the `name_kana` field to the
form and list views.
In the search view, use `name_kana_search` rather than `name_kana`: a search
view compares the term to the column as typed, and that field is what
normalizes the term first. Readings are then normalized on create and write,
and a term typed into the model's lookup finds the record whichever kana form
it is in.

For a reading of something other than the name -- an address, say -- inherit
`kana.mixin` alone and declare the `Char` fields with `kana=True`. They are
normalized on create and write like a name reading; add an `onchange` on them
if the form should show the stored form before saving.

`name.kana.mixin` needs `kana.mixin` beside it, which is where the
normalization lives. Neither derives from the other, so a module extending
`kana.mixin` reaches every model that took it.
