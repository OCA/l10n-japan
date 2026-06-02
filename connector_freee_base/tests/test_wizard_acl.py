# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import AccessError
from odoo.tests.common import new_test_user

from .common import FreeeBackendTestCommon


class TestFreeeWizardACL(FreeeBackendTestCommon):
    """The README documents a dual-permission model: every record-mapping
    wizard requires *both* ``group_freee_admin`` (gates the form button)
    *and* the native Odoo group needed to edit the underlying record
    (e.g. ``account.group_account_manager`` for the account-item
    wizard). The wizard's ``action_select`` must therefore NOT use
    ``sudo()`` — the standard ACL on the target ``write`` is the second
    gate.

    The dual-permission rule applies to every master wizard *except*
    the company picker (which writes to ``freee.backend`` and is
    intentionally ``sudo()`` so a freee-admin without other Odoo rights
    can bind a company id during onboarding)."""

    def _freee_admin_only_user(self, login):
        return new_test_user(
            self.env,
            login=login,
            groups="connector_freee_base.group_freee_admin",
        )

    def test_account_item_wizard_blocks_freee_admin_without_accounting(self):
        income_account = self.env["account.account"].search(
            [
                ("account_type", "=", "income"),
                ("company_ids", "in", self.env.company.id),
            ],
            limit=1,
        )
        # Build the wizard + a fake fetched row as the privileged
        # test admin — what we want to assert is that the *commit*
        # step (action_select → account.write) fails for a freee
        # admin who lacks accounting-manager rights, not that the
        # wizard scaffolding itself is locked down.
        wizard = self.env["freee.account.item.fetch.wizard"].create(
            {
                "account_id": income_account.id,
                "backend_id": self.backend.id,
            }
        )
        line = self.env["freee.account.item.fetch.wizard.line"].create(
            {
                "wizard_id": wizard.id,
                "external_id": 9001,
                "name": "Sales",
            }
        )
        user = self._freee_admin_only_user("freee-admin-only")
        with self.assertRaises(AccessError):
            line.with_user(user).action_select()

    def test_walletable_wizard_blocks_freee_admin_without_accounting(self):
        journal = self.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", self.env.company.id)],
            limit=1,
        )
        wizard = self.env["freee.walletable.fetch.wizard"].create(
            {"journal_id": journal.id, "backend_id": self.backend.id}
        )
        line = self.env["freee.walletable.fetch.wizard.line"].create(
            {
                "wizard_id": wizard.id,
                "external_id": 4430264,
                "name": "三菱ＵＦＪ（法人）（API）",
                "walletable_type": "bank_account",
            }
        )
        user = self._freee_admin_only_user("freee-admin-walletable")
        with self.assertRaises(AccessError):
            line.with_user(user).action_select()

    def test_partner_wizard_blocks_freee_admin_without_partner_write(self):
        partner = self.env["res.partner"].create({"name": "Acme Co."})
        wizard = self.env["freee.partner.fetch.wizard"].create(
            {"partner_id": partner.id, "backend_id": self.backend.id}
        )
        line = self.env["freee.partner.fetch.wizard.line"].create(
            {
                "wizard_id": wizard.id,
                "external_id": 103504311,
                "name": "[demo]株式会社freee企画",
            }
        )
        # base.group_user has read-only on res.partner; write requires
        # base.group_partner_manager.
        user = self._freee_admin_only_user("freee-admin-partner")
        with self.assertRaises(AccessError):
            line.with_user(user).action_select()

    def test_item_wizard_blocks_freee_admin_without_product_write(self):
        product = self.env["product.template"].create({"name": "Mapped Product"})
        wizard = self.env["freee.item.fetch.wizard"].create(
            {"product_tmpl_id": product.id, "backend_id": self.backend.id}
        )
        line = self.env["freee.item.fetch.wizard.line"].create(
            {
                "wizard_id": wizard.id,
                "external_id": 241425920,
                "name": "イラストデザイン",
            }
        )
        user = self._freee_admin_only_user("freee-admin-item")
        with self.assertRaises(AccessError):
            line.with_user(user).action_select()

    def test_section_wizard_blocks_freee_admin_without_analytic_rights(self):
        plan = self.env["account.analytic.plan"].create({"name": "ACL Plan"})
        analytic = self.env["account.analytic.account"].create(
            {"name": "営業部", "plan_id": plan.id}
        )
        wizard = self.env["freee.section.fetch.wizard"].create(
            {"analytic_account_id": analytic.id, "backend_id": self.backend.id}
        )
        line = self.env["freee.section.fetch.wizard.line"].create(
            {
                "wizard_id": wizard.id,
                "external_id": 3615078,
                "name": "営業部",
            }
        )
        user = self._freee_admin_only_user("freee-admin-section")
        with self.assertRaises(AccessError):
            line.with_user(user).action_select()

    def test_tax_code_wizard_blocks_freee_admin_without_accounting(self):
        tax = self.env["account.tax"].create(
            {"name": "JP 10%", "amount": 10.0, "type_tax_use": "sale"}
        )
        wizard = self.env["freee.tax.code.fetch.wizard"].create(
            {"tax_id": tax.id, "backend_id": self.backend.id}
        )
        line = self.env["freee.tax.code.fetch.wizard.line"].create(
            {
                "wizard_id": wizard.id,
                "code": 129,
                "name": "課税売上10%",
            }
        )
        user = self._freee_admin_only_user("freee-admin-tax")
        with self.assertRaises(AccessError):
            line.with_user(user).action_select()
