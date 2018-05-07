# -*- coding: utf-8 -*-
# Copyright 2018 Quartile Limited
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo.tests import common
from odoo.exceptions import ValidationError


class L10nJpPartnerTitleQwebCase(common.TransactionCase):

    def setUp(self):
        super(L10nJpPartnerTitleQwebCase, self).setUp()
        self.japanese = self.env.ref('base.lang_ja_JP')
        self.japanese.active = True
        self.title_sama = self.env.ref(
            'l10n_jp_partner_title_qweb.res_partner_title_sama')
        self.title_onchuu = self.env.ref(
            'l10n_jp_partner_title_qweb.res_partner_title_onchuu')
        # company partner
        self.partner1 = self.env.ref('base.res_partner_1')
        # individual partner
        self.partner_address1 = self.env.ref('base.res_partner_address_1')

    def test_00_title_constraint(self):
        with self.assertRaises(ValidationError):
            self.title_sama.write({'for_company': True})

    def test_01_title_constraint(self):
        with self.assertRaises(ValidationError):
            self.env['res.partner.title'].create(
                {'name': 'title1',
                 'lang_id': self.japanese.id,
                 'for_company': True}
            )

    def test_02_title_proposal(self):
        partner = self.partner1
        partner.lang = self.japanese.code
        self.assertEqual(partner.title, self.title_onchuu)

    def test_03_title_proposal(self):
        partner = self.partner_address1
        partner.lang = self.japanese.code
        self.assertEqual(partner.title, self.title_sama)
