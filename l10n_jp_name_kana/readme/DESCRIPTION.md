Adds a phonetic reading (カナ / ふりがな) to contacts, and provides the abstract
model that carries the same behaviour to other models.

A reading is the sort key and the lookup key for a name written in kanji, since
kanji has no usable collation order and staff search by pronunciation. It is
only useful if the same pronunciation always produces the same stored string, so
kana values are normalized on write. Administrators choose the format: a global
one, overridable per model. Full-width katakana is used when nothing is
configured.
