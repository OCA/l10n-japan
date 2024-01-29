# Copyright 2024 Quartile Limited
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestResPartner(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Test Partner"})

    def test_onchange_zip_valid(self):
        """Test _onchange_zip with a valid zip code."""
        # When country is Japan -> address should be updated
        self.partner.country_id = self.env.ref("base.jp").id
        self.partner.zip = "810-0041"
        self.partner._onchange_zip()
        self.assertTrue(
            self.partner.city, "City should be updated with a valid zip code."
        )
        self.assertTrue(
            self.partner.street, "Street should be updated with a valid zip code."
        )
        # When no country is set -> address should be updated
        self.partner.country_id = False
        self.partner.zip = "540-0002"
        self.partner._onchange_zip()
        self.assertTrue(
            self.partner.city, "City should be updated with a valid zip code."
        )
        self.assertTrue(
            self.partner.street, "Stree should be updated with a valid zip code."
        )
        self.assertTrue(
            self.partner.country_id, "Country should be updated with a valid zip code."
        )

    def test_onchange_zip_another_country(self):
        # When country is US -> address should NOT be updated
        self.partner.country_id = self.env.ref("base.us").id
        self.partner.zip = "810-0041"
        self.partner._onchange_zip()
        self.assertFalse(self.partner.city)
        self.assertFalse(self.partner.street)

    def test_onchange_zip_invalid(self):
        """Test _onchange_zip with an invalid zip code."""
        self.partner.zip = "999-9999"
        self.partner._onchange_zip()
        self.assertFalse(self.partner.city)
        self.assertFalse(self.partner.street)
        self.assertFalse(self.partner.country_id)
        self.partner.zip = "11111"
        with self.assertRaises(UserError):
            self.partner._onchange_zip()
        self.partner.zip = "test"
        with self.assertRaises(UserError):
            self.partner._onchange_zip()
