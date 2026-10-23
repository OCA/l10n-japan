# Copyright 2024 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from requests import PreparedRequest, Session

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, _super_send


class TestResPartner(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.japan = cls.env.ref("base.jp")
        cls.us = cls.env.ref("base.us")
        cls.env.company.country_id = cls.japan
        cls.us_company = cls.env["res.company"].create(
            {"name": "US Company", "country_id": cls.us.id}
        )
        cls.partner = cls.env["res.partner"].create({"name": "Test Partner"})

    @classmethod
    def _request_handler(cls, s: Session, r: PreparedRequest, /, **kw):
        if r.url.startswith("https://zipcloud.ibsnet.co.jp"):
            return _super_send(s, r, **kw)
        return super()._request_handler(s, r, **kw)

    def test_onchange_zip_valid(self):
        """Test _onchange_zip with a valid zip code."""
        # When country is Japan -> address should be updated
        self.partner.country_id = self.japan
        self.partner.zip = "８１０００４１"
        self.partner._onchange_zip()
        self.assertEqual(self.partner.zip, "810-0041")
        self.assertTrue(
            self.partner.city, "City should be updated with a valid zip code."
        )
        self.assertTrue(
            self.partner.street, "Street should be updated with a valid zip code."
        )
        # When no country is set -> address should be updated
        self.partner.country_id = False
        self.partner.zip = "5400002"
        self.partner._onchange_zip()
        self.assertEqual(self.partner.zip, "540-0002")
        self.assertTrue(
            self.partner.city, "City should be updated with a valid zip code."
        )
        self.assertTrue(
            self.partner.street, "Stree should be updated with a valid zip code."
        )
        self.assertEqual(
            self.partner.country_id,
            self.japan,
            "Country should be updated with a valid zip code.",
        )

    def test_onchange_zip_digits_format(self):
        self.env["res.config.settings"].create(
            {"l10n_jp_zip_format": "digits"}
        ).execute()
        self.partner.country_id = self.japan
        self.partner.zip = "〒810-0041"
        self.partner._onchange_zip()
        self.assertEqual(self.partner.zip, "8100041")
        self.assertTrue(self.partner.city)

    def test_onchange_zip_another_country(self):
        # When country is US -> address should NOT be updated
        self.partner.country_id = self.us
        self.partner.zip = "8100041"
        self.partner._onchange_zip()
        self.assertEqual(self.partner.zip, "8100041")
        self.assertFalse(self.partner.city)
        self.assertFalse(self.partner.street)
        # No country, company in the US -> address should NOT be updated
        partner = (
            self.env["res.partner"]
            .with_company(self.us_company)
            .create({"name": "Shared Partner"})
        )
        partner.zip = "8100041"
        partner._onchange_zip()
        self.assertEqual(partner.zip, "8100041")
        self.assertFalse(partner.city)
        self.assertFalse(partner.country_id)

    def test_onchange_zip_invalid(self):
        """Test _onchange_zip with an invalid zip code."""
        self.partner.zip = "999-9999"
        self.partner._onchange_zip()
        self.assertFalse(self.partner.city)
        self.assertFalse(self.partner.street)
        self.assertFalse(self.partner.country_id)
        for zipcode in ("11111", "test", "81000411"):
            with self.subTest(zipcode=zipcode):
                self.partner.zip = zipcode
                with self.assertRaises(UserError):
                    self.partner._onchange_zip()
