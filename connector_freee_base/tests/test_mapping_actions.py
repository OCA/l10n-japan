# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""The *Pick from freee* buttons (``action_open_*_wizard``) open a picker
wizard bound to the record. These cover the open actions on every
freee-mapped master model; the ``action_clear_*`` counterparts are covered by
``test_master_mapping_clear``.
"""

from .common import FreeeBackendTestCommon


class TestMappingActions(FreeeBackendTestCommon):
    def setUp(self):
        super().setUp()
        # The picker wizards default ``backend_id`` to the first *authorized*
        # backend (it is required), so authorize the test backend.
        self.backend.sudo().write({"state": "authorized", "external_company_id": 1234})

    def _assert_opens(self, action, wizard_model):
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], wizard_model)
        self.assertTrue(self.env[wizard_model].browse(action["res_id"]).exists())

    def test_open_account_item_wizard_on_account(self):
        account = self.env["account.account"].create(
            {"name": "freee test income", "code": "FRTST1", "account_type": "income"}
        )
        self._assert_opens(
            account.action_open_freee_account_item_wizard(),
            "freee.account.item.fetch.wizard",
        )

    def test_open_tax_code_wizard_on_tax(self):
        tax = self.env["account.tax"].create(
            {"name": "freee test tax", "amount": 10.0, "type_tax_use": "sale"}
        )
        self._assert_opens(
            tax.action_open_freee_tax_code_wizard(),
            "freee.tax.code.fetch.wizard",
        )

    def test_open_partner_wizard(self):
        partner = self.env["res.partner"].create({"name": "freee test partner"})
        self._assert_opens(
            partner.action_open_freee_partner_wizard(),
            "freee.partner.fetch.wizard",
        )

    def test_open_item_wizard_on_product(self):
        product = self.env["product.template"].create({"name": "freee test product"})
        self._assert_opens(
            product.action_open_freee_item_wizard(),
            "freee.item.fetch.wizard",
        )

    def test_open_section_wizard_on_analytic(self):
        plan = self.env["account.analytic.plan"].create({"name": "freee test plan"})
        analytic = self.env["account.analytic.account"].create(
            {"name": "freee test dept", "plan_id": plan.id}
        )
        self._assert_opens(
            analytic.action_open_freee_section_wizard(),
            "freee.section.fetch.wizard",
        )

    def test_open_account_item_and_walletable_wizards_on_journal(self):
        journal = self.env["account.journal"].create(
            {"name": "freee test journal", "type": "sale", "code": "FRTJ"}
        )
        self._assert_opens(
            journal.action_open_freee_account_item_wizard(),
            "freee.account.item.fetch.wizard",
        )
        self._assert_opens(
            journal.action_open_freee_walletable_wizard(),
            "freee.walletable.fetch.wizard",
        )
