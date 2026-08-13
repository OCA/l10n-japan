# Copyright 2025 Quartile
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import date

from odoo import Command
from odoo.tests.common import TransactionCase


class TestBillingFromCutoff(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.invoice_model = cls.env["account.move"]
        cls.partner_1 = cls.env["res.partner"].create({"name": "Test Partner 1"})
        cls.partner_2 = cls.env["res.partner"].create(
            {"name": "Test Partner 2", "is_not_for_billing": True}
        )
        cls.payment_term = cls.env.ref(
            "account.account_payment_term_end_following_month"
        )
        cls.payment_term.line_ids.write(
            {"has_cutoff_day": True, "months": 1, "cutoff_day": 20}
        )
        cls.product = cls.env.ref("product.product_product_4")
        cls.currency_eur = cls.env.ref("base.EUR")
        cls.currency_eur.active = True
        cls.currency_usd = cls.env.ref("base.USD")
        cls.currency_usd.active = True
        cls.account_revenue = cls.env["account.account"].search(
            [
                ("account_type", "=", "income"),
                ("company_ids", "in", cls.env.company.id),
            ],
            limit=1,
        )

    def create_invoice(self, partner, currency, invoice_date):
        """Returns an open invoice"""
        invoice = self.invoice_model.create(
            {
                "partner_id": partner.id,
                "currency_id": currency.id,
                "move_type": "out_invoice",
                "invoice_date": invoice_date,
                "invoice_payment_term_id": self.payment_term.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 100.00,
                            "name": "Test",
                            "account_id": self.account_revenue.id,
                        }
                    )
                ],
            }
        )
        invoice.action_post()
        return invoice

    def _run_create_billing_wizard(self, cutoff):
        wiz = (
            self.env["wiz.account.billing.cutoff"]
            .with_context(default_bill_type="out_invoice")
            .create({"cutoff_date": cutoff})
        )
        return wiz.action_create_billings()

    def _created_billing_ids(self, action):
        dom = action.get("domain") or []
        for field, op, value in dom:
            if field == "id" and op == "in":
                return list(value)
        return []

    def test_billing_created_for_summary_partner(self):
        inv_1 = self.create_invoice(
            partner=self.partner_1,
            currency=self.currency_usd,
            invoice_date=date(2025, 9, 15),
        )
        inv_2 = self.create_invoice(
            partner=self.partner_2,
            currency=self.currency_usd,
            invoice_date=date(2025, 9, 15),
        )
        inv_3 = self.create_invoice(
            partner=self.partner_1,
            currency=self.currency_usd,
            invoice_date=date(2025, 9, 21),
        )
        inv_4 = self.create_invoice(
            partner=self.partner_2,
            currency=self.currency_usd,
            invoice_date=date(2025, 9, 21),
        )
        inv_5 = self.create_invoice(
            partner=self.partner_1,
            currency=self.currency_eur,
            invoice_date=date(2025, 9, 21),
        )
        inv_6 = self.create_invoice(
            partner=self.partner_2,
            currency=self.currency_eur,
            invoice_date=date(2025, 9, 21),
        )
        # 1) cutoff = 2025-09-30 → only partner_1’s 2025-09-15 (inv_1) qualifies
        action = self._run_create_billing_wizard(date(2025, 9, 30))
        billing_ids = self._created_billing_ids(action)
        billings = self.env["account.billing"].browse(billing_ids)
        self.assertEqual(len(billings), 1)
        self.assertEqual(billings.billing_line_ids.mapped("move_id"), inv_1)
        self.assertEqual(billings.threshold_date, date(2025, 9, 30))
        # 2) cutoff = 2025-10-31 → partner_1 USD inv_3 added to existing draft billing,
        # partner_1 EUR inv_5 creates a new billing. 2 billings returned
        # (1 updated + 1 new).
        billing_usd = billings
        action = self._run_create_billing_wizard(date(2025, 10, 31))
        billing_ids = self._created_billing_ids(action)
        billings = self.env["account.billing"].browse(billing_ids)
        self.assertEqual(len(billings), 2)
        self.assertIn(billing_usd.id, billings.ids)
        self.assertEqual(billing_usd.billing_line_ids.mapped("move_id"), inv_1 | inv_3)
        self.assertEqual(billing_usd.threshold_date, date(2025, 10, 31))
        billing_eur = billings - billing_usd
        self.assertEqual(billing_eur.billing_line_ids.mapped("move_id"), inv_5)
        self.assertEqual(billing_eur.threshold_date, date(2025, 10, 31))
        # 3) Re-run same cutoff → nothing new
        # (already billed and still in billed/draft states)
        action = self._run_create_billing_wizard(date(2025, 10, 31))
        billing_ids = self._created_billing_ids(action)
        billings = self.env["account.billing"].browse(billing_ids)
        self.assertFalse(billings)
        # 4) Cancel existing billings, include partner_2 in billing, rerun → 4 billings
        #    (p1 USD/EUR again because previous are cancelled; plus p2 USD/EUR)
        self.env["account.billing"].search([]).write({"state": "cancel"})
        (inv_2 | inv_4 | inv_6).is_not_for_billing = False
        action = self._run_create_billing_wizard(date(2025, 10, 31))
        billing_ids = self._created_billing_ids(action)
        billings = self.env["account.billing"].browse(billing_ids)
        self.assertEqual(len(billings), 4)
        self.assertEqual(
            billings.billing_line_ids.mapped("move_id"),
            inv_1 | inv_2 | inv_3 | inv_4 | inv_5 | inv_6,
        )
        for billing in billings:
            billing.validate_billing()

    def test_billing_on_due_date_is_not_reused(self):
        inv_1 = self.create_invoice(
            partner=self.partner_1,
            currency=self.currency_usd,
            invoice_date=date(2025, 9, 15),
        )
        action = self._run_create_billing_wizard(date(2025, 9, 30))
        billing_1 = self.env["account.billing"].browse(
            self._created_billing_ids(action)
        )
        self.assertEqual(billing_1.threshold_date_type, "invoice_date")
        billing_1.threshold_date_type = "invoice_date_due"

        inv_2 = self.create_invoice(
            partner=self.partner_1,
            currency=self.currency_usd,
            invoice_date=date(2025, 9, 21),
        )
        action = self._run_create_billing_wizard(date(2025, 10, 31))
        billing_2 = self.env["account.billing"].browse(
            self._created_billing_ids(action)
        )
        # The draft billing based on due dates is left untouched, and a new billing
        # is created for the moves selected from the cutoff date.
        self.assertNotIn(billing_1.id, billing_2.ids)
        self.assertEqual(billing_1.billing_line_ids.mapped("move_id"), inv_1)
        self.assertEqual(billing_1.threshold_date, date(2025, 9, 30))
        self.assertEqual(billing_2.billing_line_ids.mapped("move_id"), inv_2)
        self.assertEqual(billing_2.threshold_date, date(2025, 10, 31))

    def test_append_does_not_lower_threshold_date(self):
        inv_1 = self.create_invoice(
            partner=self.partner_1,
            currency=self.currency_usd,
            invoice_date=date(2025, 9, 15),
        )
        action = self._run_create_billing_wizard(date(2025, 9, 30))
        billing = self.env["account.billing"].browse(self._created_billing_ids(action))
        billing.threshold_date = date(2025, 11, 30)

        inv_2 = self.create_invoice(
            partner=self.partner_1,
            currency=self.currency_usd,
            invoice_date=date(2025, 9, 21),
        )
        self._run_create_billing_wizard(date(2025, 10, 31))

        self.assertEqual(billing.billing_line_ids.mapped("move_id"), inv_1 | inv_2)
        self.assertEqual(billing.threshold_date, date(2025, 11, 30))
        billing.validate_billing()
