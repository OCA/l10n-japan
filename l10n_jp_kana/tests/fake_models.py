# Copyright 2026 Quartile (https://www.quartile.co)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class KanaTestRecord(models.Model):
    """A consumer of both mixins, loaded only by the tests.

    The module ships abstract models alone, so without this nothing here would
    exercise their create, write, onchange and search paths.
    """

    _name = "kana.test.record"
    _description = "Kana Test Record"
    _inherit = ["kana.mixin", "name.kana.mixin"]

    name = fields.Char(required=True)


class KanaTestAlias(models.Model):
    """A consumer of kana.mixin on its own, naming the field it normalizes.

    Kept apart from KanaTestRecord so each mixin is covered standing alone.
    """

    _name = "kana.test.alias"
    _description = "Kana Test Alias"
    _inherit = ["kana.mixin"]

    name = fields.Char(required=True)
    alias_kana = fields.Char(kana=True)
