# Copyright 2026 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models

from .name_kana_mixin import KANA_FORMAT_PARAM


class IrConfigParameter(models.Model):
    _inherit = "ir.config_parameter"

    def _is_kana_format_key(self, key):
        # The global key, or a per-model one below it. Matching on the bare
        # prefix would also claim an unrelated key that merely starts with the
        # same text, and refuse it as an invalid kana format.
        return bool(key) and (
            key == KANA_FORMAT_PARAM or key.startswith(f"{KANA_FORMAT_PARAM}.")
        )

    def _check_kana_format_value(self, value):
        """Refuse an unusable format at configuration time.

        Hooked here rather than on res.config.settings so that it covers the
        settings page, a hand edit under Technical > System Parameters and a
        programmatic set_param alike. The per-model formats have no settings
        field, so they are typed by hand into a free-text parameter; without
        this the typo would only surface later, when someone saves a record.
        """
        if value:
            self.env["name.kana.mixin"]._validate_kana_format(value)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if self._is_kana_format_key(vals.get("key")):
                self._check_kana_format_value(vals.get("value"))
        return super().create(vals_list)

    def write(self, vals):
        if "value" in vals:
            keys = set(self.mapped("key")) | {vals.get("key")}
            if any(self._is_kana_format_key(key) for key in keys):
                self._check_kana_format_value(vals["value"])
        return super().write(vals)
