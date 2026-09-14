# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""``action_select`` write-back coverage for every master-data wizard.

``test_journal_account_item`` and ``test_journal_walletable`` already
cover the two journal-bound wizards. These cover the equivalent path on
the remaining five — partner, item, section, tax code,
company — so a typo in the dict passed to ``parent.write({...})`` would
fail a test instead of silently writing the wrong column."""

from .common import FreeeBackendTestCommon


class TestMasterWizardSelect(FreeeBackendTestCommon):
    def test_partner_wizard_writes_freee_fields(self):
        partner = self.env["res.partner"].create({"name": "Acme Co."})
        wizard = self.env["freee.partner.fetch.wizard"].create(
            {"partner_id": partner.id, "backend_id": self.backend.id}
        )
        line = self.env["freee.partner.fetch.wizard.line"].create(
            {
                "wizard_id": wizard.id,
                "external_id": 103504311,
                "code": "P-555",
                "name": "[demo]株式会社freee企画",
            }
        )

        action = line.action_select()

        self.assertEqual(partner.freee_partner_id, 103504311)
        self.assertEqual(partner.freee_partner_code, "P-555")
        self.assertEqual(partner.freee_partner_name, "[demo]株式会社freee企画")
        self.assertEqual(action["type"], "ir.actions.act_window_close")

    def test_partner_wizard_code_optional(self):
        """freee partners may have no ``code`` — the wizard line stores
        ``False`` and the write-back must not blow up on it."""
        partner = self.env["res.partner"].create({"name": "Acme Co."})
        wizard = self.env["freee.partner.fetch.wizard"].create(
            {"partner_id": partner.id, "backend_id": self.backend.id}
        )
        line = self.env["freee.partner.fetch.wizard.line"].create(
            {
                "wizard_id": wizard.id,
                "external_id": 7777,
                "name": "コード無しPartner",
            }
        )
        line.action_select()
        self.assertEqual(partner.freee_partner_id, 7777)
        self.assertFalse(partner.freee_partner_code)
        self.assertEqual(partner.freee_partner_name, "コード無しPartner")

    def test_item_wizard_writes_freee_fields(self):
        product = self.env["product.template"].create({"name": "Consulting"})
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

        action = line.action_select()

        self.assertEqual(product.freee_item_id, 241425920)
        self.assertEqual(product.freee_item_name, "イラストデザイン")
        self.assertEqual(action["type"], "ir.actions.act_window_close")

    def test_section_wizard_writes_freee_fields(self):
        plan = self.env["account.analytic.plan"].create({"name": "Test Plan"})
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

        action = line.action_select()

        self.assertEqual(analytic.freee_section_id, 3615078)
        self.assertEqual(analytic.freee_section_name, "営業部")
        self.assertEqual(action["type"], "ir.actions.act_window_close")

    def test_tax_code_wizard_writes_freee_fields(self):
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

        action = line.action_select()

        self.assertEqual(tax.freee_tax_code, 129)
        self.assertEqual(tax.freee_tax_name, "課税売上10%")
        self.assertEqual(action["type"], "ir.actions.act_window_close")

    def test_company_wizard_writes_external_company_onto_backend(self):
        """Company picker writes ``external_company_id`` /
        ``external_company_name`` onto the freee.backend itself — not a
        master record like the other wizards."""
        wizard = self.env["freee.company.fetch.wizard"].create(
            {"backend_id": self.backend.id}
        )
        line = self.env["freee.company.fetch.wizard.line"].create(
            {
                "wizard_id": wizard.id,
                "external_id": "12195334",
                "name": "開発用テスト事業所",
                "display_name": "開発用テスト事業所",
                "role": "admin",
            }
        )

        action = line.action_select()

        self.assertEqual(self.backend.external_company_id, 12195334)
        self.assertEqual(self.backend.external_company_name, "開発用テスト事業所")
        self.assertEqual(action["type"], "ir.actions.act_window_close")

    def test_company_wizard_falls_back_to_name_when_display_name_blank(self):
        """``display_name`` is freee's preferred caption; when freee
        returns no display_name the wizard must fall back to ``name``."""
        wizard = self.env["freee.company.fetch.wizard"].create(
            {"backend_id": self.backend.id}
        )
        line = self.env["freee.company.fetch.wizard.line"].create(
            {
                "wizard_id": wizard.id,
                "external_id": "99999",
                "name": "Fallback Co.",
                "display_name": False,
            }
        )
        line.action_select()
        self.assertEqual(self.backend.external_company_name, "Fallback Co.")
