# Copyright 2026 Quartile (https://www.quartile.co)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo.tests import TransactionCase

from ..models.res_partner import normalize_jp_zip


class TestPartnerZip(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env["res.partner"]
        cls.japan = cls.env.ref("base.jp")
        cls.us = cls.env.ref("base.us")
        cls.env.company.country_id = cls.japan
        cls.us_company, cls.no_country_company = cls.env["res.company"].create(
            [
                {"name": "US Company", "country_id": cls.us.id},
                {"name": "No Country Company"},
            ]
        )

    def test_normalize_jp_zip(self):
        for value in (
            "1530064",
            "153-0064",
            "１５３－００６４",
            "１５３ー００６４",
            "153−0064",
            "〒153-0064",
            "〒 153 0064 ",
        ):
            with self.subTest(value=value):
                self.assertEqual(normalize_jp_zip(value), "153-0064")
                self.assertEqual(normalize_jp_zip(value, hyphen=False), "1530064")
        for value in ("153", "153-00", "15300640", "000-000A", "_", "SW1A 1AA"):
            with self.subTest(value=value):
                self.assertEqual(normalize_jp_zip(value), value)
                self.assertEqual(normalize_jp_zip(value, hyphen=False), value)
        self.assertFalse(normalize_jp_zip(False))

    def test_create(self):
        partners = self.Partner.create(
            [
                {"name": "Japan", "zip": "1530064", "country_id": self.japan.id},
                {"name": "No country", "zip": "1530064"},
                {"name": "US", "zip": "1530064", "country_id": self.us.id},
                {
                    "name": "US company",
                    "zip": "1530064",
                    "company_id": self.us_company.id,
                },
                {
                    "name": "No country company",
                    "zip": "1530064",
                    "company_id": self.no_country_company.id,
                },
            ]
        )
        self.assertEqual(
            partners.mapped("zip"),
            ["153-0064", "153-0064", "1530064", "1530064", "1530064"],
        )

    def test_create_context(self):
        # A shared contact goes by the current company, and defaults count.
        for partner_model in (
            self.Partner.with_company(self.us_company),
            self.Partner.with_context(default_country_id=self.us.id),
        ):
            with self.subTest(context=partner_model.env.context):
                partner = partner_model.create({"name": "A", "zip": "1530064"})
                self.assertEqual(partner.zip, "1530064")

    def test_write(self):
        partners = self.Partner.create(
            [
                {"name": "Japan", "country_id": self.japan.id},
                {"name": "No country"},
                {"name": "US", "country_id": self.us.id},
                {"name": "US company", "company_id": self.us_company.id},
            ]
        )
        partners.write({"zip": "8100001"})
        self.assertEqual(
            partners.mapped("zip"), ["810-0001", "810-0001", "8100001", "8100001"]
        )
        # A non-string zip, as an RPC caller may send, fails for no partner.
        partners.write({"zip": 1530064})
        self.assertEqual(
            partners.mapped("zip"), ["153-0064", "153-0064", "1530064", "1530064"]
        )
        japan = partners[0]
        japan.write({"zip": "8100001", "country_id": self.us.id})
        self.assertEqual(japan.zip, "8100001")

    def test_write_becomes_japanese(self):
        # The postcode already stored is formatted once the contact is Japanese.
        by_country, by_clearing, by_company = self.Partner.create(
            [
                {"name": "A", "zip": "8100001", "country_id": self.us.id},
                {"name": "B", "zip": "8100001", "country_id": self.us.id},
                {"name": "C", "zip": "8100001", "company_id": self.us_company.id},
            ]
        )
        by_country.write({"country_id": self.japan.id})
        by_clearing.write({"country_id": False})
        by_company.write({"company_id": self.env.company.id})
        self.assertEqual(
            (by_country | by_clearing | by_company).mapped("zip"),
            ["810-0001", "810-0001", "810-0001"],
        )

    def test_address_sync(self):
        # Core syncs the address between a company and its contacts without
        # going through write(), with the value as written.
        parent = self.Partner.create(
            {"name": "Parent", "is_company": True, "country_id": self.japan.id}
        )
        child = self.Partner.create({"name": "Child", "parent_id": parent.id})
        parent.write({"zip": "8100001"})
        self.assertEqual(child.zip, "810-0001")
        child.write({"zip": "1530064"})
        self.assertEqual(parent.zip, "153-0064")

    def test_digits_format(self):
        self.env["res.config.settings"].create(
            {"l10n_jp_zip_format": "digits"}
        ).execute()
        partner = self.Partner.create({"name": "A", "zip": "〒153-0064"})
        self.assertEqual(partner.zip, "1530064")
        partner.write({"zip": "８１０－０００１"})
        self.assertEqual(partner.zip, "8100001")
