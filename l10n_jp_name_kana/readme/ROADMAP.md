Changing a kana format does not rewrite the readings that are already stored.
Only readings saved after the change follow the new format; the older ones keep
the format they were saved in, and because a search term is normalized to the
current format, they stop being found by it until they are saved again.

Rewriting them from the request that changes the setting is what this module
deliberately does not do: readings are close to unique, so there is nothing to
group the updates by, and one UPDATE per row on a table of any size outlasts the
request, rolls it back, and leaves the format unchangeable with no diagnosable
error. Doing it safely needs a batched background job, which is left for a
future version.

Until then, pick the format when the module is installed. If it has to change
afterwards, re-save the affected readings separately -- writing a reading back
through the ORM normalizes it to the current format.
