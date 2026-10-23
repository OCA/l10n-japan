# Copyright 2024 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import requests

from odoo import api, models
from odoo.exceptions import UserError

from odoo.addons.l10n_jp_partner_zip.models.res_partner import normalize_jp_zip


class ZipSearchMixin(models.AbstractModel):
    _name = "zip.search.mixin"
    _description = "ZIP Search Mixin"

    def _make_zip_request(self, request_url):
        try:
            response = requests.get(request_url, timeout=10)
            response.raise_for_status()  # Raise HTTPError for bad responses
            return response.json()
        except requests.exceptions.HTTPError as http_err:
            return {"status": response.status_code, "message": str(http_err)}
        except requests.exceptions.RequestException as req_err:
            return {"status": 500, "message": f"Request error: {str(req_err)}"}

    def _l10n_jp_zip_search_applies(self):
        """Return whether the postcode of the record is to be looked up."""
        self.ensure_one()
        return not self.country_id or self.country_id == self.env.ref("base.jp")

    @api.onchange("zip")
    def _onchange_zip(self):
        if not self.zip or not self._l10n_jp_zip_search_applies():
            return
        zipcode = normalize_jp_zip(self.zip, hyphen=False)
        if not zipcode.isdigit() or len(zipcode) != 7:
            raise UserError(self.env._("Postcode should be 7 digits."))
        self.zip = normalize_jp_zip(
            self.zip, hyphen=self.env["res.partner"]._l10n_jp_zip_hyphen()
        )
        request_url = f"https://zipcloud.ibsnet.co.jp/api/search?zipcode={zipcode}"
        response_data = self._make_zip_request(request_url)
        if response_data["status"] != 200:
            raise UserError(response_data["message"])
        japan = self.env.ref("base.jp")
        self.state_id = False
        self.city = False
        self.street = False
        address_data = response_data["results"]
        if address_data:
            self.state_id = self.env["res.country.state"].search(
                [("name", "=", address_data[0]["address1"])], limit=1
            )
            if (
                not self.state_id
                and self.env.lang != "ja_JP"
                and "ja_JP" in self.env["res.lang"].get_installed()
            ):
                self.state_id = (
                    self.env["res.country.state"]
                    .with_context(lang="ja_JP")
                    .search([("name", "=", address_data[0]["address1"])], limit=1)
                )
            self.city = address_data[0]["address2"]
            self.street = address_data[0]["address3"]
            self.country_id = japan
