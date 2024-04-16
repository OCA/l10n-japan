# Copyright 2024 Quartile Limited
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging
import re

import requests

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"
    _timeout = 10

    corporate_number = fields.Char(help="Japanese Corporate Registration Number")
    duplicate_corp_number_warning_message = fields.Text(
        compute="_compute_duplicate_corp_number_warning_message"
    )

    @api.depends("corporate_number")
    def _compute_duplicate_corp_number_warning_message(self):
        for rec in self:
            rec.duplicate_corp_number_warning_message = False
            if rec.corporate_number:
                domain = [("corporate_number", "=", rec.corporate_number)]
                if (
                    rec.id
                ):  # Exclude the current record from the search to avoid self-detection
                    domain.append(("id", "!=", rec.id))
                duplicates = self.env["res.partner"].search(domain, limit=1)
                company = self.env.company
                if duplicates and company.duplicate_corp_number_behavior == "warning":
                    rec.duplicate_corp_number_warning_message = company.warning_message

    @api.constrains("corporate_number")
    def _check_corporate_number(self):
        for record in self:
            duplicate_rec = self.env["res.partner"].search(
                [
                    ("corporate_number", "=", record.corporate_number),
                    ("id", "!=", record.id),
                ],
                limit=1,
            )
            company = self.env.company
            if duplicate_rec and company.duplicate_corp_number_behavior == "error":
                raise ValidationError(_(company.error_message))
            if record.corporate_number and not re.match(
                r"^\d{13}$", record.corporate_number
            ):
                raise ValidationError(_("Corporate Number must be 13 digits."))

    def fetch_corporate_info(self):
        self.ensure_one()
        if self.corporate_number:
            data = self._fetch_gbizinfo(self.corporate_number)
            hojin_info = data.get("hojin-infos", [{}])[0]  # get a first element
            address_vals = self._split_address(hojin_info.get("location"))
            partner_vals = {
                "name": hojin_info.get("name"),
                "street": hojin_info.get("location"),
                **address_vals,
            }
            self.write(partner_vals)

    def _split_address(self, location):
        # in Japan
        country_id = self.env.ref("base.jp").id
        # remove Japanese ZIP code
        address_without_zip = re.sub(r"\d{3}-\d{4}", "", location).strip()
        pattern = """(...??[都道府県])((?:旭川|伊達|石狩|盛岡|奥州|田村|南相馬|那須塩原|東村山|武蔵村山|羽村|十日町|上越|
富山|野々市|大町|蒲郡|四日市|姫路|大和郡山|廿日市|下松|岩国|田川|大村|宮古|富良野|別府|佐伯|黒部|小諸|塩尻|玉野|
周南)市|(?:余市|高市|[^市]{2,3}?)郡(?:玉村|大町|.{1,5}?)[町村]|(?:.{1,4}市)?[^町]{1,4}?区|.{1,7}?[市町村])(.+)"""
        result = re.match(pattern, address_without_zip)
        if result:
            state_name = result.group(1)
            city = result.group(2)
            street = result.group(3)
        # Stateの取得（存在しない場合はNone）
        # 都道府県を日本語化するモジュール(base_country_state_translatable)依存
        # 都道府県名は日本語翻訳済とする
        state_id = (
            self.env["res.country.state"]
            .search(
                [("name", "like", state_name), ("country_id", "=", country_id)], limit=1
            )
            .id
        )
        return {
            "country_id": country_id,
            "state_id": state_id,
            "city": city,
            "street": street,
        }

    def _fetch_gbizinfo(self, corporate_number):
        # gBizINFOのエンドポイントURL + 法人番号
        endpoint = f"https://info.gbiz.go.jp/hojin/v1/hojin/{corporate_number}"
        access_token = (
            self.env["ir.config_parameter"].sudo().get_param("gbizinfo_access_token")
        )
        headers = {
            "Accept": "application/json",
            "X-hojinInfo-api-token": access_token,
        }

        # APIリクエストを実行
        try:
            response = requests.get(
                endpoint, headers=headers, timeout=(self._timeout, self._timeout)
            )
            if response.status_code == 200:
                # 成功した場合、JSONデータを抽出
                return response.json()
            else:
                # エラーがあった場合、問題をログに記録
                error_msg = (
                    f"Failed to fetch data from gBizINFO: {response.status_code}"
                )
                _logger.error(error_msg)
                return None
        except requests.Timeout:
            _logger.error("Request timed out.")
            return None
        except requests.RequestException as e:
            _logger.error(f"An error occurred: {e}")
            return None
