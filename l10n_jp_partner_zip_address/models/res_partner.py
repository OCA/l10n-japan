# Copyright 2024 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class ResPartner(models.Model):
    _name = "res.partner"
    _inherit = ["res.partner", "zip.search.mixin"]

    def _l10n_jp_zip_search_applies(self):
        # The same contacts as those whose postcode l10n_jp_partner_zip formats.
        return self._l10n_jp_zip_is_japanese()
