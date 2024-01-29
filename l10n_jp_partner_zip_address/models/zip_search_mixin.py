# Copyright 2024 Quartile Limited
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

import requests

from odoo import _, api, models
from odoo.exceptions import UserError

try:
    import jaconv
except (ImportError, IOError) as err:
    logging.getLogger(__name__).warning(err)


class ZipSearchMixin(models.AbstractModel):
    _name = "zip.search.mixin"

    def sanitize_zip(self, zipcode):
        field = jaconv.z2h(zipcode, ascii=True, digit=True).replace("-", "")
        if not field.isdigit():
            raise UserError(_("Only digits are allowed."))
        elif len(field) != 7:
            field = False
            raise UserError(_("Postcode should be 7 digits."))
        return field

    def _make_zip_request(self, request_url):
        try:
            response = requests.get(request_url)
            response.raise_for_status()  # Raise HTTPError for bad responses
            return response.json()
        except requests.exceptions.HTTPError as http_err:
            return {"status": response.status_code, "message": str(http_err)}
        except requests.exceptions.RequestException as req_err:
            return {"status": 500, "message": f"Request error: {str(req_err)}"}

    @api.onchange("zip")
    def _onchange_zip(self):
        japan = self.env.ref("base.jp")
        if (self.country_id and self.country_id != japan) or not self.zip:
            return
        self.zip = self.sanitize_zip(self.zip)
        request_url = f"http://zipcloud.ibsnet.co.jp/api/search?zipcode={self.zip}"
        response_data = self._make_zip_request(request_url)
        if response_data["status"] != 200:
            raise UserError(response_data["message"])
        self.state_id = False
        self.city = False
        self.street = False
        address_data = response_data["results"]
        if address_data:
            self.state_id = self.env["res.country.state"].search(
                [("name", "=", address_data[0]["address1"])], limit=1
            )
            if not self.state_id and self.env.lang != "ja_JP":
                self.state_id = (
                    self.env["res.country.state"]
                    .with_context(lang="ja_JP")
                    .search([("name", "=", address_data[0]["address1"])], limit=1)
                )
            self.city = address_data[0]["address2"]
            self.street = address_data[0]["address3"]
            self.country_id = japan
