# Copyright 2023 Quartile Limited
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase


class TestAccountReportRegistrationNumber(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.country_jp = cls.env.ref("base.jp")
        cls.country_us = cls.env.ref("base.us")
        cls.company = cls.env["res.company"].create(
            {"name": "Test Company JP", "country_id": cls.country_jp.id}
        )
        cls.partner = cls.env["res.partner"].create(
            {"name": "Test Partner JP", "country_id": cls.country_jp.id}
        )
        cls.general_journal = cls.env["account.journal"].create(
            {
                "name": "General Journal",
                "code": "GEN",
                "type": "bank",
                "company_id": cls.company.id,
            }
        )
        cls.move = cls.env["account.move"].create(
            {
                "name": "Test Account Move",
                "company_id": cls.company.id,
                "partner_id": cls.partner.id,
                "journal_id": cls.general_journal.id,
            }
        )

    def test_show_registration_number(self):
        self.assertTrue(self.move._show_registration_number())
        # Test company JP, partner non-JP
        self.partner.country_id = self.country_us
        self.assertFalse(self.move._show_registration_number())
        # Test company non-JP, partner JP
        self.company.account_fiscal_country_id = self.country_us
        self.partner.country_id = self.country_jp
        self.assertFalse(self.move._show_registration_number())
