# Copyright 2026 Quartile (https://www.quartile.co)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import api, models

from .kana_mixin import KANA_FORMAT_PARAM


class IrConfigParameter(models.Model):
    _inherit = "ir.config_parameter"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if self._is_kana_format_key(vals.get("key")):
                self._check_kana_format_value(vals.get("value"))
        return super().create(vals_list)

    def write(self, vals):
        # Against the key the record ends up with, so a rename onto a kana key
        # cannot carry an unchecked value in.
        for record in self:
            if self._is_kana_format_key(vals.get("key", record.key)):
                self._check_kana_format_value(vals.get("value", record.value))
        return super().write(vals)

    def _is_kana_format_key(self, key):
        # A bare prefix match would also claim unrelated keys.
        return bool(key) and (
            key == KANA_FORMAT_PARAM or key.startswith(f"{KANA_FORMAT_PARAM}.")
        )

    def _check_kana_format_value(self, value):
        # Here rather than on res.config.settings, so a hand-typed per-model
        # parameter is refused too.
        if value:
            self.env["kana.mixin"]._validate_kana_format(value)
