# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""Every freee master-data mapping must be un-mappable again.

The journal walletable already had ``action_clear_freee_walletable``
(covered by test_journal_walletable). These cover the equivalent
``action_clear_freee_*`` added for the other masters — account item
(on account *and* journal), partner, item, section and
tax code — so an operator can revert a wrong pick without editing the
DB by hand. Each clear wipes both the id and the display-name field.
"""

from .common import FreeeBackendTestCommon


class TestMasterMappingClear(FreeeBackendTestCommon):
    def test_clear_account_item_on_account(self):
        account = self.env["account.account"].search(
            [
                ("account_type", "=", "income"),
                ("company_ids", "in", self.env.company.id),
            ],
            limit=1,
        )
        account.write(
            {"freee_account_item_id": 9001, "freee_account_item_name": "売上高"}
        )
        account.action_clear_freee_account_item()
        self.assertFalse(account.freee_account_item_id)
        self.assertFalse(account.freee_account_item_name)

    def test_clear_account_item_override_on_journal(self):
        journal = self.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", self.env.company.id)],
            limit=1,
        )
        journal.write(
            {"freee_account_item_id": 7777, "freee_account_item_name": "EC売上"}
        )
        journal.action_clear_freee_account_item()
        self.assertFalse(journal.freee_account_item_id)
        self.assertFalse(journal.freee_account_item_name)

    def test_clear_account_item_keeps_walletable_independent(self):
        """The journal carries two independent mappings (account-item
        override and settlement walletable); clearing one must not wipe
        the other."""
        journal = self.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", self.env.company.id)],
            limit=1,
        )
        journal.write(
            {
                "freee_account_item_id": 7777,
                "freee_account_item_name": "EC売上",
                "freee_walletable_id": 4430264,
                "freee_walletable_type": "bank_account",
                "freee_walletable_name": "三菱ＵＦＪ（法人）（API）",
            }
        )
        journal.action_clear_freee_account_item()
        self.assertFalse(journal.freee_account_item_id)
        self.assertEqual(journal.freee_walletable_id, 4430264)
        journal.action_clear_freee_walletable()
        self.assertFalse(journal.freee_walletable_id)

    def test_clear_partner(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Acme Co.",
                "freee_partner_id": 555,
                "freee_partner_code": "P-555",
                "freee_partner_name": "アクメ商事",
            }
        )
        partner.action_clear_freee_partner()
        self.assertFalse(partner.freee_partner_id)
        self.assertFalse(partner.freee_partner_code)
        self.assertFalse(partner.freee_partner_name)

    def test_clear_item_on_product(self):
        product = self.env["product.template"].create(
            {
                "name": "Mapped Product",
                "freee_item_id": 33012,
                "freee_item_name": "コンサル",
            }
        )
        product.action_clear_freee_item()
        self.assertFalse(product.freee_item_id)
        self.assertFalse(product.freee_item_name)

    def test_clear_section_on_analytic_account(self):
        plan = self.env["account.analytic.plan"].create({"name": "freee Plan"})
        analytic = self.env["account.analytic.account"].create(
            {
                "name": "freee Section",
                "plan_id": plan.id,
                "freee_section_id": 3668411,
                "freee_section_name": "営業部",
            }
        )
        analytic.action_clear_freee_section()
        self.assertFalse(analytic.freee_section_id)
        self.assertFalse(analytic.freee_section_name)

    def test_clear_tax_code(self):
        tax = self.env["account.tax"].create(
            {
                "name": "JP 10%",
                "amount": 10.0,
                "type_tax_use": "sale",
                "freee_tax_code": 21,
                "freee_tax_name": "課税売上10%",
            }
        )
        tax.action_clear_freee_tax_code()
        self.assertFalse(tax.freee_tax_code)
        self.assertFalse(tax.freee_tax_name)

    def test_clear_is_idempotent_on_recordset(self):
        """The clear actions follow the walletable pattern (plain
        ``self.write`` — no ``ensure_one``), so they work on a
        multi-record set and are a no-op when nothing is mapped."""
        partners = self.env["res.partner"].create(
            [
                {"name": "A", "freee_partner_id": 1},
                {"name": "B"},
            ]
        )
        partners.action_clear_freee_partner()
        self.assertFalse(any(partners.mapped("freee_partner_id")))
