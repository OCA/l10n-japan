# Copyright 2026 Quartile (https://www.quartile.co)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import unicodedata
from collections.abc import Set as AbstractSet

import jaconv

from odoo import api, models, tools
from odoo.exceptions import UserError

DEFAULT_KANA_FORMAT = "full_width_katakana"

# A model-specific key is this one suffixed with the model name.
KANA_FORMAT_PARAM = "l10n_jp_kana.format"

KANA_FORMAT_SELECTION = [
    ("full_width_katakana", "Full-width Katakana"),
    ("half_width_katakana", "Half-width Katakana"),
    ("hiragana", "Hiragana"),
]

SUPPORTED_KANA_FORMATS = dict(KANA_FORMAT_SELECTION)


class KanaMixin(models.AbstractModel):
    """Normalize the Char fields declared with ``kana=True`` on create and write."""

    _name = "kana.mixin"
    _description = "Kana Mixin"

    def _valid_field_parameter(self, field, name):
        return name == "kana" or super()._valid_field_parameter(field, name)

    @api.model_create_multi
    def create(self, vals_list):
        return super().create([self._normalize_kana_vals(vals) for vals in vals_list])

    def write(self, vals):
        return super().write(self._normalize_kana_vals(vals))

    def _normalize_kana_vals(self, vals):
        kana_fields = self._get_kana_fields()
        to_normalize = [name for name in kana_fields if name in vals]
        if not to_normalize:
            return vals
        vals = dict(vals)
        for field_name in to_normalize:
            owner = self.env[kana_fields[field_name]]
            vals[field_name] = owner._normalize_name_kana_write_value(vals[field_name])
        return vals

    def _normalize_kana_field(self, field_name):
        """Normalize one field in place; intended to be called from the model's
        @api.onchange.
        """
        owner = self.env[self._get_kana_fields()[field_name]]
        for record in self:
            record[field_name] = owner._normalize_name_kana_write_value(
                record[field_name]
            )

    @api.model
    @tools.ormcache()
    def _get_kana_fields(self):
        """The fields to normalize, each mapped to the model that stores it.

        An inherited field (e.g. name_kana on product.product) uses the format of
        the parent model (product.template), since the value is stored there.
        """
        kana_fields = {}
        for name, field in self._fields.items():
            source = field.inherited_field if field.inherited else field
            if getattr(source, "kana", False):
                kana_fields[name] = source.model_name
        return kana_fields

    @api.model
    def _get_kana_format(self):
        """A model-specific parameter wins over the global one.

        System parameters, not company fields: partner and product rows are
        shared between companies.
        """
        get_param = self.env["ir.config_parameter"].sudo().get_param
        return (
            get_param(f"{KANA_FORMAT_PARAM}.{self._name}")
            or get_param(KANA_FORMAT_PARAM)
            or DEFAULT_KANA_FORMAT
        )

    @api.model
    def _validate_kana_format(self, kana_format):
        if kana_format in SUPPORTED_KANA_FORMATS:
            return
        raise UserError(
            self.env._(
                "%(format)s is not a valid kana format. Check the "
                "%(parameter)s system parameters; expected one of: "
                "%(supported)s.",
                format=kana_format,
                parameter=f"{KANA_FORMAT_PARAM}*",
                supported=", ".join(SUPPORTED_KANA_FORMATS),
            )
        )

    @api.model
    def _normalize_name_kana(self, value):
        """NFKC (folds the width of kana, ASCII and digits), single spaces, then
        the configured kana format.
        """
        if not isinstance(value, str) or not value.strip():
            return value
        kana_format = self._get_kana_format()
        self._validate_kana_format(kana_format)
        value = unicodedata.normalize("NFKC", value)
        value = " ".join(value.split())
        if kana_format == "hiragana":
            return jaconv.kata2hira(value)
        value = jaconv.hira2kata(value)
        if kana_format == "half_width_katakana":
            return jaconv.z2h(value, kana=True, digit=False, ascii=False)
        return value

    @api.model
    def _normalize_name_kana_write_value(self, value):
        """A blank -- including the IME's U+3000 -- becomes False, so the column
        holds NULL rather than a truthy string with no reading in it.
        """
        if isinstance(value, str) and not value.strip():
            return False
        return self._normalize_name_kana(value)

    @api.model
    def _normalize_name_kana_search_value(self, value):
        """A blank term stays as typed; as False an ilike would match everything.
        Any set counts as a collection: the ORM rewrites ``=`` into ``in``.
        """
        if isinstance(value, (list, tuple, AbstractSet)):
            return [self._normalize_name_kana(item) for item in value]
        return self._normalize_name_kana(value)
