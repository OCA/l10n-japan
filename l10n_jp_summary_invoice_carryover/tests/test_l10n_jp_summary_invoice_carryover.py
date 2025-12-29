# Copyright 2025 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import date

from odoo.fields import Command
from odoo.tests.common import TransactionCase


class TestSummaryInvoiceCarryover(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create(
            {
                "name": "test company",
                "currency_id": cls.env.ref("base.JPY").id,
                "country_id": cls.env.ref("base.jp").id,
                "tax_calculation_rounding_method": "round_globally",
            }
        )
        cls.env = cls.env(
            context={"allowed_company_ids": [cls.company.id], "tracking_disable": True}
        )
        account_receivable = cls.env["account.account"].create(
            {"code": "recv", "name": "Receivable", "account_type": "asset_receivable"}
        )
        cls.account_income = cls.env["account.account"].create(
            {"code": "income", "name": "Income", "account_type": "income"}
        )
        account_bank = cls.env["account.account"].create(
            {"code": "bank", "name": "Bank", "account_type": "asset_cash"}
        )
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner",
                "property_account_receivable_id": account_receivable.id,
            }
        )
        tax_group = cls.env["account.tax.group"].create({"name": "Tax Group"})
        cls.tax_10 = cls.env["account.tax"].create(
            {
                "name": "Test Tax 10%",
                "amount": 10.0,
                "type_tax_use": "sale",
                "company_id": cls.company.id,
                "tax_group_id": tax_group.id,
            }
        )
        cls.env["account.journal"].create(
            {"code": "SALE", "name": "Sales Journal", "type": "sale"}
        )
        cls.bank_journal = cls.env["account.journal"].create(
            {
                "code": "BNK",
                "name": "Bank Journal",
                "type": "bank",
                "default_account_id": account_bank.id,
                "inbound_payment_method_line_ids": [
                    Command.create(
                        {
                            "payment_method_id": cls.env.ref(
                                "account.account_payment_method_manual_in"
                            ).id,
                            "payment_account_id": account_bank.id,
                        }
                    )
                ],
            }
        )

    def _create_invoice(self, amount, tax, move_type="out_invoice"):
        invoice = self.env["account.move"].create(
            {
                "move_type": move_type,
                "partner_id": self.partner.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "test line",
                            "account_id": self.account_income.id,
                            "quantity": 1,
                            "price_unit": amount,
                            "tax_ids": [Command.set(tax.ids)],
                        }
                    )
                ],
            }
        )
        invoice.action_post()
        return invoice

    def _create_billing(self, amount_or_invoices, billing_date=None, validate=False):
        """Create a billing. If amount is given, create an invoice first."""
        if isinstance(amount_or_invoices, int | float):
            invoices = self._create_invoice(amount_or_invoices, self.tax_10)
        else:
            invoices = amount_or_invoices
        billing = self.env["account.billing"].create(
            {
                "partner_id": self.partner.id,
                "bill_type": "out_invoice",
                "date": billing_date or date(2025, 1, 15),
                "billing_line_ids": [
                    Command.create({"move_id": inv.id}) for inv in invoices
                ],
            }
        )
        if validate:
            billing.validate_billing()
            self.env.flush_all()
        return billing

    def _register_payment(self, invoice, amount):
        """Register a payment for an invoice."""
        payment = self.env["account.payment"].create(
            {
                "journal_id": self.bank_journal.id,
                "partner_id": invoice.partner_id.id,
                "amount": amount,
                "payment_type": "inbound",
                "partner_type": "customer",
            }
        )
        payment.action_post()
        receivable_line = invoice.line_ids.filtered(
            lambda x: x.account_id.account_type == "asset_receivable"
        )
        payment_line = payment.move_id.line_ids.filtered(
            lambda x: x.account_id.account_type == "asset_receivable"
        )
        (receivable_line + payment_line).reconcile()
        return payment

    def test_compute_prev_billing_id(self):
        billing1 = self._create_billing(1000, date(2025, 1, 15), validate=True)
        self.assertFalse(billing1.prev_billing_id)
        billing2 = self._create_billing(2000, date(2025, 2, 15))
        self.assertEqual(billing2.prev_billing_id, billing1)

    def test_compute_carryover_amounts_no_previous(self):
        billing = self._create_billing(1000)
        self.assertEqual(billing.prev_billed_amount, 0)
        self.assertEqual(billing.payment_amount, 0)
        self.assertEqual(billing.carryover_amount, 0)
        self.assertEqual(billing.total_billed_amount, 1100)

    def test_compute_carryover_amounts_with_previous(self):
        self._create_billing(1000, date(2025, 1, 15), validate=True)
        billing2 = self._create_billing(2000, date(2025, 2, 15))
        self.assertEqual(billing2.prev_billed_amount, 1100)
        self.assertEqual(billing2._get_prev_billed_amount(), 1100)
        self.assertEqual(billing2.payment_amount, 0)
        self.assertEqual(billing2._get_payment_amount(), 0)
        self.assertEqual(billing2.carryover_amount, 1100)
        # Total billed amount is previous total plus current total
        self.assertEqual(billing2.total_billed_amount, 3300)

    def test_compute_carryover_amounts_with_partial_payment(self):
        billing1 = self._create_billing(1000, date(2025, 1, 15), validate=True)
        self._register_payment(billing1.billing_line_ids.move_id, 500)
        billing2 = self._create_billing(2000, date(2025, 2, 15))
        self.assertEqual(billing2.prev_billed_amount, 1100)
        self.assertEqual(billing2.payment_amount, 500)
        self.assertEqual(billing2.carryover_amount, 600)

    def test_compute_carryover_amounts_with_credit_note(self):
        # Prev billing: invoice 1000 (1100 with tax) + credit note 200 (220 with tax)
        # Net: 1100 - 220 = 880
        invoice = self._create_invoice(1000, self.tax_10)
        credit_note = self._create_invoice(200, self.tax_10, move_type="out_refund")
        billing1 = self._create_billing(
            invoice + credit_note, date(2025, 1, 15), validate=True
        )
        self.assertEqual(billing1.amount_total, 880)
        billing2 = self._create_billing(2000, date(2025, 2, 15))
        self.assertEqual(billing2.prev_billed_amount, 880)
        self.assertEqual(billing2.payment_amount, 0)
        self.assertEqual(billing2.carryover_amount, 880)

    def test_manual_override_prev_billed_amount(self):
        self._create_billing(1000, date(2025, 1, 15), validate=True)
        billing2 = self._create_billing(2000, date(2025, 2, 15))
        billing2.use_prev_billed_amount_manual = True
        billing2.prev_billed_amount_manual = 5000
        self.assertEqual(billing2.carryover_amount, 5000)
        self.assertEqual(billing2._get_prev_billed_amount(), 5000)
        # Test that zero override works (not treated as falsy)
        billing2.prev_billed_amount_manual = 0
        self.assertEqual(billing2._get_prev_billed_amount(), 0)
        self.assertEqual(billing2.carryover_amount, 0)

    def test_manual_override_payment_amount(self):
        self._create_billing(1000, date(2025, 1, 15), validate=True)
        billing2 = self._create_billing(2000, date(2025, 2, 15))
        billing2.use_payment_amount_manual = True
        billing2.payment_amount_manual = 300
        self.assertEqual(billing2._get_payment_amount(), 300)
        self.assertEqual(billing2.carryover_amount, 800)

    def test_prev_billing_candidates(self):
        billing1 = self._create_billing(1000, date(2025, 1, 15), validate=True)
        billing2 = self._create_billing(1500, date(2025, 2, 15), validate=True)
        billing3 = self._create_billing(2000, date(2025, 3, 15))
        self.assertIn(billing1, billing3.prev_billing_candidate_ids)
        self.assertIn(billing2, billing3.prev_billing_candidate_ids)
        self.assertEqual(billing3.prev_billing_id, billing2)

    def test_validate_freezes_carryover_amounts(self):
        """Validation copies computed values to manual fields to freeze them."""
        billing1 = self._create_billing(1000, date(2025, 1, 15), validate=True)
        billing2 = self._create_billing(2000, date(2025, 2, 15))
        self.assertFalse(billing2.use_prev_billed_amount_manual)
        self.assertFalse(billing2.use_payment_amount_manual)
        self.assertEqual(billing2.carryover_amount, 1100)
        billing2.validate_billing()
        self.env.flush_all()
        # Toggles are now on with frozen values
        self.assertTrue(billing2.use_prev_billed_amount_manual)
        self.assertTrue(billing2.use_payment_amount_manual)
        self.assertEqual(billing2.prev_billed_amount_manual, 1100)
        self.assertEqual(billing2.payment_amount_manual, 0)
        # Register payment on billing1 after billing2 is validated
        self._register_payment(billing1.billing_line_ids.move_id, 500)
        # Carryover amounts remain frozen
        self.assertEqual(billing2.carryover_amount, 1100)
