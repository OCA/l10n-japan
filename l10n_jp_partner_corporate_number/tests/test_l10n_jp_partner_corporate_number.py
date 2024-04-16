# Copyright 2024 Quartile Limited
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestPartnerCorporateNumber(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super(TestPartnerCorporateNumber, cls).setUpClass()
        cls.env = cls.env(
            context=dict(cls.env.context, tracking_disable=True, no_open=True)
        )
        cls.company = cls.env["res.company"].create(
            {
                "name": "Test Company",
            }
        )
        cls.env.user.company_id = cls.company.id
        cls.company.duplicate_corp_number_behavior = "error"

    def test_partner_corporate_number(self):
        # Test for creating a partner with a unique corporate number
        partner = self.env["res.partner"].create(
            {"name": "Test Partner", "corporate_number": "8000012010038"}
        )
        self.assertEqual(partner.corporate_number, "8000012010038")
        partner.fetch_corporate_info()
        self.assertEqual(partner.name, "デジタル庁")
        self.assertEqual(partner.street, "紀尾井町１番３号東京ガーデンテラス紀尾井町")
        self.assertEqual(partner.city, "千代田区")
        self.assertEqual(partner.country_id.name, "Japan")
        # Test that duplicates raise a ValidationError
        with self.assertRaises(ValidationError):
            self.env["res.partner"].create(
                {"name": "Duplicate Partner", "corporate_number": "8000012010038"}
            )
        # Switching company behavior to warning
        self.company.duplicate_corp_number_behavior = "warning"
        duplicate_partner = self.env["res.partner"].create(
            {"name": "Duplicate Partner", "corporate_number": "8000012010038"}
        )
        self.assertNotEqual(
            duplicate_partner.duplicate_corp_number_warning_message,
            False,
            "Warning message should be set",
        )
