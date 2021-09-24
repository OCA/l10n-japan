# Copyright 2018-2019 Quartile Limited
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo.exceptions import ValidationError
from odoo.tests import common


class L10nJpPartnerTitleQwebCase(common.TransactionCase):
    def setUp(self):
        super(L10nJpPartnerTitleQwebCase, self).setUp()
        self.japanese = self.env.ref("base.lang_ja_JP")
        self.japanese.active = True
        self.title_sama = self.env.ref(
            "l10n_jp_partner_title_qweb.res_partner_title_sama"
        )
        self.title_onchuu = self.env.ref(
            "l10n_jp_partner_title_qweb.res_partner_title_onchuu"
        )
        # company partner
        self.partner1 = self.env.ref("base.res_partner_1")
        # individual partner not linked to user
        self.partner2 = self.env.ref("base.res_partner_address_1")
        # individual partner linked to non-internal user
        self.partner3 = self.env.ref("base.partner_demo_portal")
        # individual partner linked to internal user
        self.partner4 = self.env.ref("base.partner_demo")
        # partner for main company
        self.partner5 = self.env.ref("base.main_company").partner_id

    def test_00_title_constraint(self):
        with self.assertRaises(ValidationError):
            self.title_sama.write({"for_company": True})

    def test_01_title_constraint(self):
        with self.assertRaises(ValidationError):
            self.env["res.partner.title"].create(
                {"name": "title1", "lang_id": self.japanese.id, "for_company": True}
            )

    def test_02_title_proposal(self):
        partner = self.partner1
        partner.lang = self.japanese.code
        self.assertEqual(partner.title, self.title_onchuu)

    def test_03_title_proposal(self):
        partner = self.partner2
        partner.lang = self.japanese.code
        self.assertEqual(partner.title, self.title_sama)

    def test_04_title_proposal(self):
        partner = self.partner3
        partner.lang = self.japanese.code
        self.assertEqual(partner.title, self.title_sama)

    def test_05_title_proposal(self):
        partner = self.partner4
        partner.lang = self.japanese.code
        self.assertFalse(partner.title)

    def test_06_title_proposal(self):
        partner = self.partner5
        partner.lang = self.japanese.code
        self.assertFalse(partner.title)
