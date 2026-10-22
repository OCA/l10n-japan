# Copyright 2026 Quartile (https://www.quartile.co)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import re
import unicodedata
from collections import defaultdict

from odoo import api, models

# Seven digits, optionally split 3-4 by a hyphen or one of the dashes people type
# for it (NFKC has already folded the full-width ones), with an optional 〒 mark.
JP_ZIP_PATTERN = re.compile(r"〒?\s*(\d{3})\s*[-‐‑‒–—―−ー]?\s*(\d{4})")


def normalize_jp_zip(value, hyphen=True):
    """Return a Japanese postcode as NNN-NNNN, or as NNNNNNN without hyphen.

    A value that does not read as exactly seven digits is returned unchanged:
    it is not ours to guess, and leaving it visible lets someone correct it.
    """
    if not value:
        return value
    match = JP_ZIP_PATTERN.fullmatch(unicodedata.normalize("NFKC", value).strip())
    if not match:
        return value
    return f"{match[1]}{'-' if hyphen else ''}{match[2]}"


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model
    def _l10n_jp_zip_hyphen(self):
        format_ = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("l10n_jp_partner_zip.format", "hyphen")
        )
        return format_ != "digits"

    def _l10n_jp_zip_is_japanese(self):
        self.ensure_one()
        # Cached, unlike env.ref(), which queries whether the record exists.
        jp_id = self.env["ir.model.data"]._xmlid_to_res_id("base.jp")
        if self.country_id:
            return self.country_id.id == jp_id
        # No country: go by the company, or the current one for a shared contact.
        company = self.company_id or self.env.company
        return company.sudo().country_id.id == jp_id

    def _l10n_jp_zip_partners(self):
        """Return the contacts of self whose postcode is Japanese."""
        return self.filtered(lambda p: p._l10n_jp_zip_is_japanese())

    def _l10n_jp_normalize_stored_zip(self):
        """Bring the stored postcodes of these Japanese contacts to the format."""
        hyphen = self._l10n_jp_zip_hyphen()
        by_zip = defaultdict(self.browse)
        for partner in self:
            zip_code = normalize_jp_zip(partner.zip, hyphen)
            if zip_code != partner.zip:
                by_zip[zip_code] |= partner
        for zip_code, group in by_zip.items():
            group.write({"zip": zip_code})

    @api.model_create_multi
    def create(self, vals_list):
        # Done on the records rather than vals_list, so that defaults count.
        partners = super().create(vals_list)
        partners.filtered("zip")._l10n_jp_zip_partners()._l10n_jp_normalize_stored_zip()
        return partners

    def write(self, vals):
        res = super().write(vals)
        # Normalize the stored values: vals may hold a non-string zip (an int
        # over RPC, say), which only the field converts to a string.
        if {"zip", "country_id", "company_id"} & vals.keys():
            self.filtered("zip")._l10n_jp_zip_partners()._l10n_jp_normalize_stored_zip()
        return res
