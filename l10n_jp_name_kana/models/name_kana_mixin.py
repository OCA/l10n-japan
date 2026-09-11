# Copyright 2026 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from collections.abc import Set as AbstractSet

import jaconv

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain

DEFAULT_KANA_FORMAT = "full_width_katakana"

# Global key. A model-specific key is this one suffixed with the model name,
# e.g. "l10n_jp_name_kana.format.res.partner".
KANA_FORMAT_PARAM = "l10n_jp_name_kana.format"

KANA_FORMAT_SELECTION = [
    ("full_width_katakana", "Full-width Katakana"),
    ("half_width_katakana", "Half-width Katakana"),
    ("hiragana", "Hiragana"),
]

SUPPORTED_KANA_FORMATS = dict(KANA_FORMAT_SELECTION)


class NameKanaMixin(models.AbstractModel):
    _name = "name.kana.mixin"
    _description = "Kana Name Mixin"

    name_kana = fields.Char(string="Name (Kana)", index="trigram")
    name_kana_search = fields.Char(
        string="Name (Kana) Search",
        compute="_compute_name_kana_search",
        search="_search_name_kana",
    )

    @api.depends("name_kana")
    def _compute_name_kana_search(self):
        for record in self:
            record.name_kana_search = record.name_kana

    @api.model
    def _search_name_kana(self, operator, value):
        """Search the stored readings with the term put in their format first.

        Backs the name_kana_search field, so that the search view and the
        contact lookup agree: both find a record whichever kana form the term
        is typed in.
        """
        return Domain(
            "name_kana", operator, self._normalize_name_kana_search_value(value)
        )

    @api.model
    def _search_display_name(self, operator, value):
        domain = super()._search_display_name(operator, value)
        kana_domain = self._search_name_kana(operator, value)
        if operator in Domain.NEGATIVE_OPERATORS:
            return Domain.AND([domain, kana_domain])
        return Domain.OR([domain, kana_domain])

    @api.model
    def _get_kana_format(self):
        """Return the format this model stores its readings in.

        A model-specific setting wins over the global one. Both are system
        parameters rather than company fields: res.partner and product.template
        rows are shared between companies by default, so a per-company format
        would let two users produce two spellings of the same row.
        """
        get_param = self.env["ir.config_parameter"].sudo().get_param
        return (
            get_param(f"{KANA_FORMAT_PARAM}.{self._name}")
            or get_param(KANA_FORMAT_PARAM)
            or DEFAULT_KANA_FORMAT
        )

    @api.model
    def _validate_kana_format(self, kana_format):
        """Raise unless the format is one this module knows how to produce.

        Checked when the parameter is written, so a typo is refused at
        configuration time, and again here, because the parameter is free text
        and could also have been set outside the ORM.
        """
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
        """Return the canonical representation of a kana name."""
        if not isinstance(value, str) or not value.strip():
            return value
        kana_format = self._get_kana_format()
        self._validate_kana_format(kana_format)
        value = " ".join(value.split())
        value = jaconv.h2z(value, kana=True, digit=False, ascii=False)
        if kana_format == "hiragana":
            return jaconv.kata2hira(value)
        value = jaconv.hira2kata(value)
        if kana_format == "half_width_katakana":
            return jaconv.z2h(value, kana=True, digit=False, ascii=False)
        return value

    @api.model
    def _normalize_name_kana_write_value(self, value):
        """Normalize a value on its way into the column.

        A blank reading is stored as no reading at all. A whitespace-only
        string is truthy, so it would otherwise count as a reading everywhere:
        it would pass a "has a reading" filter and sort among the readings. The
        search counterpart below deliberately does the opposite and keeps a
        blank as typed, because a blank term must not turn into a search for an
        empty reading.
        """
        if isinstance(value, str) and not value.strip():
            return False
        return self._normalize_name_kana(value)

    @api.model
    def _normalize_name_kana_search_value(self, value):
        """Normalize a search term, which may be a single value or a collection.

        `in` and `not in` carry a collection, and the ORM rewrites `=` into `in`
        with an ``OrderedSet``, so this has to accept any set as well as a list
        or a tuple -- the same types core treats as a collection here. Checking
        only list and tuple lets the set through unnormalized, and the kana
        condition then searches for the term as typed and matches nothing.
        """
        if isinstance(value, (list, tuple, AbstractSet)):
            return [self._normalize_name_kana(item) for item in value]
        return self._normalize_name_kana(value)

    @api.model_create_multi
    def create(self, vals_list):
        normalized_vals_list = []
        for vals in vals_list:
            vals = dict(vals)
            if "name_kana" in vals:
                vals["name_kana"] = self._normalize_name_kana_write_value(
                    vals["name_kana"]
                )
            normalized_vals_list.append(vals)
        return super().create(normalized_vals_list)

    def write(self, vals):
        if "name_kana" in vals:
            vals = dict(vals)
            vals["name_kana"] = self._normalize_name_kana_write_value(vals["name_kana"])
        return super().write(vals)
