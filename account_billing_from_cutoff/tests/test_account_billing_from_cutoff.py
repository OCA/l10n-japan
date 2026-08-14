# Copyright 2025 Quartile (https://www.quartile.co)
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
        cls.bank_a, cls.bank_b = cls.env["res.partner.bank"].create(
            [
                {
                    "acc_number": "TEST-BANK-A",
                    "partner_id": cls.env.company.partner_id.id,
                    # Required to post a customer invoice that points to it
                    "allow_out_payment": True,
                },
                {
                    "acc_number": "TEST-BANK-B",
                    "partner_id": cls.env.company.partner_id.id,
                    "allow_out_payment": True,
                },
            ]
        )
        cls.account_revenue = cls.env["account.account"].search(
            [
                ("account_type", "=", "income"),
                ("company_ids", "in", cls.env.company.id),
            ],
            limit=1,
        )

    def create_invoice(
        self,
        partner,
        currency,
        invoice_date,
        partner_bank=None,
        move_type="out_invoice",
    ):
        """Returns an open invoice"""
        invoice = self.invoice_model.create(
            {
                "partner_id": partner.id,
                "currency_id": currency.id,
                "move_type": move_type,
                "invoice_date": invoice_date,
                "partner_bank_id": partner_bank.id if partner_bank else False,
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

    def _created_billings(self, action, partner):
        """Billings of the given partner, the wizard also picking up any other
        invoice of the database that is due for billing."""
        billings = self.env["account.billing"].browse(self._created_billing_ids(action))
        return billings.filtered(lambda x: x.partner_id == partner)

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

    def test_invoice_without_bank_joins_bank_of_the_new_billing(self):
        inv_bank = self.create_invoice(
            partner=self.partner_1,
            currency=self.currency_usd,
            invoice_date=date(2025, 9, 15),
            partner_bank=self.bank_a,
        )
        # Created last, so that its group is the first to be processed and no
        # billing it could be added to exists yet when it is.
        inv_no_bank = self.create_invoice(
            partner=self.partner_1,
            currency=self.currency_usd,
            invoice_date=date(2025, 9, 15),
        )
        action = self._run_create_billing_wizard(date(2025, 9, 30))
        billing = self._created_billings(action, self.partner_1)
        # The invoice without a recipient bank carries no remittance instruction,
        # so it is billed together with the one that has a bank.
        self.assertEqual(len(billing), 1)
        self.assertEqual(billing.remit_to_bank_id, self.bank_a)
        self.assertEqual(
            billing.billing_line_ids.mapped("move_id"), inv_bank | inv_no_bank
        )
        # The remit-to bank is consistent with the invoices, so the billing of
        # both can be validated.
        billing.validate_billing()

    def test_invoice_without_bank_joins_first_bank_of_the_new_billings(self):
        # bank_b comes first, so it is the bank the invoices would have been
        # given by default, and the one the invoice without a bank follows.
        self.bank_b.sequence = 1
        # Created first, so that its group is processed last and the billings of
        # the other groups already exist by the time it is.
        inv_no_bank = self.create_invoice(
            partner=self.partner_1,
            currency=self.currency_usd,
            invoice_date=date(2025, 9, 15),
        )
        # bank_b's group is not the first one to be processed either, so only
        # the sequence of the banks can bring the invoice to it.
        inv_b = self.create_invoice(
            partner=self.partner_1,
            currency=self.currency_usd,
            invoice_date=date(2025, 9, 15),
            partner_bank=self.bank_b,
        )
        inv_a = self.create_invoice(
            partner=self.partner_1,
            currency=self.currency_usd,
            invoice_date=date(2025, 9, 15),
            partner_bank=self.bank_a,
        )
        action = self._run_create_billing_wizard(date(2025, 9, 30))
        billings = self._created_billings(action, self.partner_1)
        self.assertEqual(len(billings), 2)
        self.assertEqual(
            billings.filtered(
                lambda x: x.remit_to_bank_id == self.bank_b
            ).billing_line_ids.mapped("move_id"),
            inv_b | inv_no_bank,
        )
        self.assertEqual(
            billings.filtered(
                lambda x: x.remit_to_bank_id == self.bank_a
            ).billing_line_ids.mapped("move_id"),
            inv_a,
        )

    def test_invoice_without_bank_joins_first_bank_of_the_draft_billings(self):
        # Same rule as above, applied to the billings of an earlier run rather
        # than to the groups of the current one.
        self.bank_b.sequence = 1
        inv_a = self.create_invoice(
            partner=self.partner_1,
            currency=self.currency_usd,
            invoice_date=date(2025, 9, 15),
            partner_bank=self.bank_a,
        )
        inv_b = self.create_invoice(
            partner=self.partner_1,
            currency=self.currency_usd,
            invoice_date=date(2025, 9, 15),
            partner_bank=self.bank_b,
        )
        action = self._run_create_billing_wizard(date(2025, 9, 30))
        billings = self._created_billings(action, self.partner_1)
        self.assertEqual(len(billings), 2)
        billing_b = billings.filtered(lambda x: x.remit_to_bank_id == self.bank_b)
        billing_a = billings - billing_b

        inv_no_bank = self.create_invoice(
            partner=self.partner_1,
            currency=self.currency_usd,
            invoice_date=date(2025, 9, 21),
        )
        action = self._run_create_billing_wizard(date(2025, 10, 31))
        # No billing is created: the invoice joins the draft billing of the
        # first bank, and only that billing is returned.
        self.assertEqual(self._created_billings(action, self.partner_1), billing_b)
        self.assertEqual(
            billing_b.billing_line_ids.mapped("move_id"), inv_b | inv_no_bank
        )
        self.assertEqual(billing_b.threshold_date, date(2025, 10, 31))
        # The billing of the other bank is left untouched.
        self.assertEqual(billing_a.billing_line_ids.mapped("move_id"), inv_a)
        self.assertEqual(billing_a.threshold_date, date(2025, 9, 30))

    def test_invoice_with_bank_joins_billing_without_bank(self):
        # A draft billing that states no remit-to bank does not state where the
        # invoices are to be remitted either, so it hosts an invoice that does
        # state one, and takes its bank.
        inv_no_bank = self.create_invoice(
            partner=self.partner_1,
            currency=self.currency_usd,
            invoice_date=date(2025, 9, 15),
        )
        action = self._run_create_billing_wizard(date(2025, 9, 30))
        billing = self._created_billings(action, self.partner_1)
        self.assertFalse(billing.remit_to_bank_id)

        inv_a = self.create_invoice(
            partner=self.partner_1,
            currency=self.currency_usd,
            invoice_date=date(2025, 9, 21),
            partner_bank=self.bank_a,
        )
        action = self._run_create_billing_wizard(date(2025, 10, 31))
        # No billing is created: the invoice joins the one that states no bank.
        self.assertEqual(self._created_billings(action, self.partner_1), billing)
        self.assertEqual(
            billing.billing_line_ids.mapped("move_id"), inv_no_bank | inv_a
        )
        self.assertEqual(billing.remit_to_bank_id, self.bank_a)

    def test_invoice_with_bank_prefers_billing_of_its_own_bank(self):
        # Where a draft billing of the invoice's own bank and one that states no
        # bank are both open, the former is the one that is used.
        inv_a = self.create_invoice(
            partner=self.partner_1,
            currency=self.currency_usd,
            invoice_date=date(2025, 9, 15),
            partner_bank=self.bank_a,
        )
        action = self._run_create_billing_wizard(date(2025, 9, 30))
        billing_a = self._created_billings(action, self.partner_1)
        self.assertEqual(billing_a.remit_to_bank_id, self.bank_a)
        billing_no_bank = self.env["account.billing"].create(
            {
                "partner_id": self.partner_1.id,
                "bill_type": "out_invoice",
                "currency_id": self.currency_usd.id,
                "threshold_date": date(2025, 9, 30),
            }
        )

        inv_a_2 = self.create_invoice(
            partner=self.partner_1,
            currency=self.currency_usd,
            invoice_date=date(2025, 9, 21),
            partner_bank=self.bank_a,
        )
        action = self._run_create_billing_wizard(date(2025, 10, 31))
        self.assertEqual(self._created_billings(action, self.partner_1), billing_a)
        self.assertEqual(billing_a.billing_line_ids.mapped("move_id"), inv_a | inv_a_2)
        # The billing that states no bank is left untouched.
        self.assertFalse(billing_no_bank.billing_line_ids)
        self.assertFalse(billing_no_bank.remit_to_bank_id)

    def test_invoice_with_bank_ignores_billing_of_another_bank_invoice(self):
        # A billing that states no remit-to bank can still be committed to one
        # by its lines, and then cannot take the invoices of another bank.
        inv_a = self.create_invoice(
            partner=self.partner_1,
            currency=self.currency_usd,
            invoice_date=date(2025, 9, 15),
            partner_bank=self.bank_a,
        )
        billing_no_bank = self.env["account.billing"].create(
            {
                "partner_id": self.partner_1.id,
                "bill_type": "out_invoice",
                "currency_id": self.currency_usd.id,
                "threshold_date": date(2025, 9, 30),
            }
        )
        # Added after the creation, so that the billing is left without a
        # remit-to bank while its line points to one.
        billing_no_bank.billing_line_ids.create(
            billing_no_bank._get_billing_line_dict(inv_a)
        )
        self.assertFalse(billing_no_bank.remit_to_bank_id)

        inv_b = self.create_invoice(
            partner=self.partner_1,
            currency=self.currency_usd,
            invoice_date=date(2025, 9, 21),
            partner_bank=self.bank_b,
        )
        action = self._run_create_billing_wizard(date(2025, 10, 31))
        # The invoice of the other bank gets a billing of its own.
        billing_b = self._created_billings(action, self.partner_1)
        self.assertNotEqual(billing_b, billing_no_bank)
        self.assertEqual(billing_b.remit_to_bank_id, self.bank_b)
        self.assertEqual(billing_b.billing_line_ids.mapped("move_id"), inv_b)
        # The billing committed to the first bank is left untouched.
        self.assertEqual(billing_no_bank.billing_line_ids.mapped("move_id"), inv_a)
        self.assertFalse(billing_no_bank.remit_to_bank_id)

    def test_appended_lines_are_sorted_by_invoice_date(self):
        inv_1 = self.create_invoice(
            partner=self.partner_1,
            currency=self.currency_usd,
            invoice_date=date(2025, 9, 15),
        )
        action = self._run_create_billing_wizard(date(2025, 9, 30))
        billing = self.env["account.billing"].browse(self._created_billing_ids(action))

        # An invoice dated before the one already billed, so that appending it
        # has to move it to the top of the billing.
        inv_2 = self.create_invoice(
            partner=self.partner_1,
            currency=self.currency_usd,
            invoice_date=date(2025, 9, 10),
        )
        self._run_create_billing_wizard(date(2025, 10, 31))
        self.assertEqual(
            billing.billing_line_ids.mapped("move_id").ids, [inv_2.id, inv_1.id]
        )

    def test_billing_created_for_vendor_bills(self):
        bill = self.create_invoice(
            partner=self.partner_1,
            currency=self.currency_usd,
            invoice_date=date(2025, 9, 15),
            move_type="in_invoice",
        )
        wiz = (
            self.env["wiz.account.billing.cutoff"]
            .with_context(default_bill_type="in_invoice")
            .create({"cutoff_date": date(2025, 9, 30)})
        )
        action = wiz.action_create_billings()
        self.assertEqual(
            action["id"], self.env.ref("account_billing.action_supplier_billing").id
        )
        billing = self._created_billings(action, self.partner_1)
        self.assertEqual(len(billing), 1)
        self.assertEqual(billing.bill_type, "in_invoice")
        self.assertEqual(billing.billing_line_ids.mapped("move_id"), bill)

    def test_no_move_to_bill(self):
        # A cutoff date no invoice of the database can fall before
        action = self._run_create_billing_wizard(date(1990, 1, 1))
        self.assertEqual(action["type"], "ir.actions.act_window_close")

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
