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
        # Two recipient banks for the company. `allow_out_payment` is required:
        # account.move._post() silently clears partner_bank_id on an inbound move
        # whose recipient bank is untrusted when the user is the superuser, which
        # tests are, and the billing would then find no remit-to bank to copy.
        cls.bank_a, cls.bank_b = cls.env["res.partner.bank"].create(
            [
                {
                    "acc_number": "JP-A-0001",
                    "partner_id": cls.company.partner_id.id,
                    "allow_out_payment": True,
                },
                {
                    "acc_number": "JP-B-0002",
                    "partner_id": cls.company.partner_id.id,
                    "allow_out_payment": True,
                },
            ]
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

    def _create_invoice(self, amount, tax, move_type="out_invoice", remit_to_bank=None):
        invoice = self.env["account.move"].create(
            {
                "move_type": move_type,
                "partner_id": self.partner.id,
                "partner_bank_id": remit_to_bank.id if remit_to_bank else False,
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

    def _create_billing(
        self,
        amount_or_invoices,
        billing_date=None,
        validate=False,
        remit_to_bank=None,
    ):
        """Create a billing. If amount is given, create an invoice first."""
        if isinstance(amount_or_invoices, int | float):
            invoices = self._create_invoice(
                amount_or_invoices, self.tax_10, remit_to_bank=remit_to_bank
            )
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

    def test_carryover_accumulates_when_nothing_paid(self):
        """Invoices from periods older than the previous one must keep being carried
        over (regression for chains of 3+ unpaid periods)."""
        self._create_billing(1000, date(2025, 1, 15), validate=True)
        self._create_billing(2000, date(2025, 2, 15), validate=True)
        # Period 3: prev = billing2, but nothing has been paid in any period.
        billing3 = self._create_billing(3000, date(2025, 3, 15))
        # The whole 1100 (period 1) + 2200 (period 2) is still outstanding.
        self.assertEqual(billing3.payment_amount, 0)
        self.assertEqual(billing3.carryover_amount, 3300)
        self.assertEqual(billing3.total_billed_amount, 6600)

    def test_carryover_counts_payment_on_older_billing(self):
        """A payment on a billing older than the previous one is reflected in the
        carryover of the current billing."""
        billing1 = self._create_billing(1000, date(2025, 1, 15), validate=True)
        self._create_billing(2000, date(2025, 2, 15), validate=True)
        # Pay period 1 in full before creating period 3.
        self._register_payment(billing1.billing_line_ids.move_id, 1100)
        billing3 = self._create_billing(3000, date(2025, 3, 15))
        # Only period 2's 2200 is still outstanding.
        self.assertEqual(billing3.payment_amount, 1100)
        self.assertEqual(billing3.carryover_amount, 2200)
        self.assertEqual(billing3.total_billed_amount, 5500)

    def test_carryover_reacts_to_later_payment_on_older_billing(self):
        """Paying a billing older than the immediate previous one, after the current
        draft already exists, must still update its carryover (reactivity flows
        through the recursive total_billed_amount dependency)."""
        billing1 = self._create_billing(1000, date(2025, 1, 15), validate=True)
        self._create_billing(2000, date(2025, 2, 15), validate=True)
        billing3 = self._create_billing(3000, date(2025, 3, 15))  # draft
        self.assertEqual(billing3.payment_amount, 0)
        self.assertEqual(billing3.carryover_amount, 3300)
        # Pay period 1 (older than billing3's previous billing) afterwards.
        self._register_payment(billing1.billing_line_ids.move_id, 1100)
        self.assertEqual(billing3.payment_amount, 1100)
        self.assertEqual(billing3.carryover_amount, 2200)
        self.assertEqual(billing3.total_billed_amount, 5500)

    def test_show_carryover_amounts_company_default(self):
        """With the partner on 'default', the company setting decides at creation."""
        self.partner.show_carryover_amounts = "default"
        self.assertTrue(self._create_billing(1000).show_carryover_amounts)
        self.company.show_carryover_amounts = False
        self.assertFalse(self._create_billing(1000).show_carryover_amounts)

    def test_show_carryover_amounts_partner_setting(self):
        """An explicit partner setting overrides the company default."""
        self.company.show_carryover_amounts = True
        self.partner.show_carryover_amounts = "no"
        self.assertFalse(self._create_billing(1000).show_carryover_amounts)
        self.partner.show_carryover_amounts = "yes"
        self.company.show_carryover_amounts = False
        self.assertTrue(self._create_billing(1000).show_carryover_amounts)

    def test_show_carryover_amounts_is_a_snapshot(self):
        """The value is taken at creation, so a per-billing adjustment is not
        discarded by later partner or company changes."""
        billing = self._create_billing(1000, date(2025, 1, 15), validate=True)
        self.assertTrue(billing.show_carryover_amounts)
        billing.show_carryover_amounts = False
        self.company.show_carryover_amounts = False
        self.company.show_carryover_amounts = True
        self.partner.show_carryover_amounts = "yes"
        self.env.flush_all()
        self.assertFalse(billing.show_carryover_amounts)

    def test_validate_billing_does_not_refreeze(self):
        """Re-validating an already-validated billing must keep the frozen manual
        values untouched."""
        self._create_billing(1000, date(2025, 1, 15), validate=True)
        billing2 = self._create_billing(2000, date(2025, 2, 15), validate=True)
        self.assertEqual(billing2.prev_billed_amount_manual, 1100)
        self.assertEqual(billing2.payment_amount_manual, 0)
        # Adjust the frozen values manually, then validate again.
        billing2.prev_billed_amount_manual = 9999
        billing2.payment_amount_manual = 7777
        billing2.validate_billing()
        self.env.flush_all()
        self.assertEqual(billing2.prev_billed_amount_manual, 9999)
        self.assertEqual(billing2.payment_amount_manual, 7777)

    def test_carryover_is_scoped_to_remit_to_bank(self):
        """Billings kept apart because their recipient banks differ are separate
        billing streams and must not carry each other's balances.

        `l10n_jp_summary_invoice` refuses to put invoices with different recipient
        banks on one billing, so the split is forced, and both land on the same
        closing date -- neither is then the other's previous billing. Counting both
        against a single previous billed amount used to report a payment that was
        never received (Payment Amount went negative).
        """
        billing_a = self._create_billing(
            1000, date(2025, 3, 15), validate=True, remit_to_bank=self.bank_a
        )
        self._create_billing(
            2000, date(2025, 3, 15), validate=True, remit_to_bank=self.bank_b
        )
        self.assertEqual(billing_a.remit_to_bank_id, self.bank_a)
        billing_a2 = self._create_billing(
            3000, date(2025, 4, 15), remit_to_bank=self.bank_a
        )
        # Only the bank A stream is in scope.
        self.assertEqual(billing_a2.prev_billing_candidate_ids, billing_a)
        self.assertEqual(billing_a2.prev_billing_id, billing_a)
        self.assertEqual(billing_a2.prev_billed_amount, 1100)
        self.assertEqual(billing_a2.payment_amount, 0)
        self.assertEqual(billing_a2.carryover_amount, 1100)
        self.assertEqual(billing_a2.total_billed_amount, 4400)

    def test_carryover_ignores_payment_in_another_bank_stream(self):
        """Settling a billing on another recipient bank leaves this stream alone."""
        self._create_billing(
            1000, date(2025, 3, 15), validate=True, remit_to_bank=self.bank_a
        )
        billing_b = self._create_billing(
            2000, date(2025, 3, 15), validate=True, remit_to_bank=self.bank_b
        )
        billing_a2 = self._create_billing(
            3000, date(2025, 4, 15), remit_to_bank=self.bank_a
        )
        self.assertEqual(billing_a2.carryover_amount, 1100)
        self._register_payment(billing_b.billing_line_ids.move_id, 2200)
        self.assertEqual(billing_a2.payment_amount, 0)
        self.assertEqual(billing_a2.carryover_amount, 1100)

    def test_carryover_reacts_to_payment_in_same_bank_stream(self):
        """Settling the previous billing of this stream clears the carryover."""
        billing_a = self._create_billing(
            1000, date(2025, 3, 15), validate=True, remit_to_bank=self.bank_a
        )
        self._create_billing(
            2000, date(2025, 3, 15), validate=True, remit_to_bank=self.bank_b
        )
        billing_a2 = self._create_billing(
            3000, date(2025, 4, 15), remit_to_bank=self.bank_a
        )
        self.assertEqual(billing_a2.carryover_amount, 1100)
        self._register_payment(billing_a.billing_line_ids.move_id, 1100)
        self.assertEqual(billing_a2.payment_amount, 1100)
        self.assertEqual(billing_a2.carryover_amount, 0)
        self.assertEqual(billing_a2.total_billed_amount, 3300)
