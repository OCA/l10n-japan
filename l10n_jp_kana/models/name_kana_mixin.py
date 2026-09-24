# Copyright 2026 Quartile (https://www.quartile.co)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models
from odoo.fields import Domain


class NameKanaMixin(models.AbstractModel):
    """Reading of the name, also searched from the display name.

    Requires kana.mixin on the same model, which is where the normalization
    this calls lives. Listed beside it rather than deriving from it: a model
    can end up with both, from two modules that know nothing of each other,
    and a derivation would then break its MRO depending on which loads first.
    """

    _name = "name.kana.mixin"
    _description = "Kana Name Mixin"

    def _valid_field_parameter(self, field, name):
        # Not a redundant copy of kana.mixin's: that one is a sibling, absent
        # from this model's MRO, and name_kana is declared here.
        return name == "kana" or super()._valid_field_parameter(field, name)

    name_kana = fields.Char(string="Name (Kana)", index="trigram", kana=True)
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
        return Domain(
            "name_kana", operator, self._normalize_name_kana_search_value(value)
        )

    @api.onchange("name_kana")
    def _onchange_name_kana(self):
        for record in self:
            record.name_kana = self._normalize_name_kana_write_value(record.name_kana)

    @api.model
    def _search_display_name(self, operator, value):
        domain = super()._search_display_name(operator, value)
        if domain is NotImplemented:  # the model asks for the default handling
            return domain
        kana_domain = self._search_name_kana(operator, value)
        if operator in Domain.NEGATIVE_OPERATORS:
            return Domain.AND([domain, kana_domain])
        return Domain.OR([domain, kana_domain])
