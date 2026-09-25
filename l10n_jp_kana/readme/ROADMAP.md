Changing a kana format does not rewrite the readings that are already stored.
Only readings saved after the change follow the new format; the older ones keep
the format they were saved in, and because a search term is normalized to the
current format, they stop being found by it until they are saved again.

Pick the format when the module is installed. If it has to change afterwards,
re-save the affected readings separately -- writing a reading back through the
ORM normalizes it to the current format.
