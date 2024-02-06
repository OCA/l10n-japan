# Copyright 2024 Quartile Limited
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestResPartner(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super(TestResPartner, cls).setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner",
            }
        )
        cls.japan_country_id = cls.env.ref("base.jp").id

    def test_onchange_zip_valid(self):
        """Test _onchange_zip with a valid zip code."""
        self.partner.country_id = self.japan_country_id
        self.partner.zip = "100-0001"
        self.partner._onchange_zip()
        self.assertTrue(
            self.partner.city, "City should be updated with a valid zip code."
        )
        self.assertTrue(
            self.partner.street, "Street should be updated with a valid zip code."
        )

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

    def test_onchange_zip_invalid(self):
        """Test _onchange_zip with an invalid zip code."""
        self.partner.zip = "111-1111"
        self.partner._onchange_zip()
        self.assertFalse(self.partner.city)
        self.assertFalse(self.partner.street)
        self.assertFalse(self.partner.country_id)
        self.partner.zip = "11111"
        with self.assertRaises(UserError):
            self.partner._onchange_zip()

        self.partner.zip = "invalid"
        with self.assertRaises(UserError):
            self.partner._onchange_zip()
