# Copyright 2024 Quartile
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import ValidationError
from odoo.fields import Command
from odoo.tests.common import TransactionCase


class TestSummaryInvoice(TransactionCase):
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
        cls.env.company = cls.company
        account_receivable = cls.env["account.account"].create(
            {
                "code": "test2",
                "name": "receivable",
                "reconcile": True,
                "account_type": "asset_receivable",
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner",
                "property_account_receivable_id": account_receivable.id,
            }
        )
        cls.bank_account = cls.env["res.partner.bank"].create(
            {
                "partner_id": cls.env.company.partner_id.id,
                "acc_number": "1234567890",
            }
        )
        cls.product = cls.env["product.product"].create({"name": "Test Product"})
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
        cls.journal = cls.env["account.journal"].create(
            {"code": "test", "name": "test", "type": "sale"}
        )
        cls.account_income = cls.env["account.account"].create(
            {
                "code": "test1",
                "name": "income",
                "account_type": "income",
            }
        )

    def _create_invoice(self, amount, tax, move_type="out_invoice", bank=None):
        invoice = (
            self.env["account.move"]
            .with_company(self.company)
            .create(
                {
                    "move_type": move_type,
                    "partner_id": self.partner.id,
                    "partner_bank_id": bank and bank.id,
                    "invoice_line_ids": [
                        Command.create(
                            {
                                "product_id": self.product.id,
                                "account_id": self.account_income.id,
                                "quantity": 1,
                                "price_unit": amount,
                                "tax_ids": [Command.set(tax.ids)],
                            }
                        )
                    ],
                }
            )
        )
        invoice.action_post()
        return invoice

    def _get_billing_tax_amount(self, billing):
        tax_totals = billing.tax_totals
        tax_group_amount_dict = {}
        for subtotal in tax_totals.get("subtotals", []):
            for group in subtotal.get("tax_groups", []):
                tax_group_id = group.get("id")
                tax_amount = group.get("tax_amount", 0.0)
                tax_group_amount_dict[tax_group_id] = tax_amount * -1
        return round(tax_group_amount_dict.get(self.tax_10.tax_group_id.id, 0), 0)

    def test_get_moves_filters_billed_and_flags(self):
        invoice = self._create_invoice(50, self.tax_10)
        invoice.write({"is_not_for_billing": True})
        billing = self.env["account.billing"].create({"partner_id": self.partner.id})
        moves = billing._get_moves(billing.threshold_date_type)
        self.assertNotIn(invoice.id, moves.ids)

    def test_constrains_invoice_not_for_billing(self):
        invoice = self._create_invoice(100, self.tax_10)
        invoice.write({"is_not_for_billing": True})
        with self.assertRaises(ValidationError):
            self.env["account.billing"].create(
                {
                    "partner_id": self.partner.id,
                    "billing_line_ids": [Command.create({"move_id": invoice.id})],
                }
            )

    def test_constrains_remit_to_bank_conflict(self):
        invoice = self._create_invoice(100, self.tax_10, bank=self.bank_account)
        other_bank = self.env["res.partner.bank"].create(
            {
                "partner_id": self.env.company.partner_id.id,
                "acc_number": "other_bank_acc",
            }
        )
        with self.assertRaises(ValidationError):
            self.env["account.billing"].create(
                {
                    "partner_id": self.partner.id,
                    "remit_to_bank_id": other_bank.id,
                    "billing_line_ids": [Command.create({"move_id": invoice.id})],
                }
            )

    def test_compute_billing_due_date(self):
        inv1 = self._create_invoice(100, self.tax_10)
        inv2 = self._create_invoice(200, self.tax_10)
        inv1.invoice_date_due = inv1.invoice_date_due.replace(day=5)
        inv2.invoice_date_due = inv2.invoice_date_due.replace(day=25)
        billing = self.env["account.billing"].create(
            {
                "partner_id": self.partner.id,
                "billing_line_ids": [
                    Command.create({"move_id": inv1.id}),
                    Command.create({"move_id": inv2.id}),
                ],
            }
        )
        self.assertEqual(billing.date_due, inv2.invoice_date_due)

    def test_update_remit_to_bank_defaulting(self):
        invoice = self._create_invoice(100, self.tax_10, bank=self.bank_account)
        billing = self.env["account.billing"].create(
            {
                "partner_id": self.partner.id,
                "billing_line_ids": [Command.create({"move_id": invoice.id})],
            }
        )
        self.assertEqual(billing.remit_to_bank_id, self.bank_account)

    def test_compute_amount_fields(self):
        inv1 = self._create_invoice(100, self.tax_10)
        inv2 = self._create_invoice(200, self.tax_10)
        billing = self.env["account.billing"].create(
            {
                "partner_id": self.partner.id,
                "billing_line_ids": [
                    Command.create({"move_id": inv1.id}),
                    Command.create({"move_id": inv2.id}),
                ],
            }
        )
        self.assertEqual(billing.amount_untaxed, 300)
        self.assertEqual(billing.amount_tax, 30)
        self.assertEqual(billing.amount_total, 330)

    def test_create_tax_adjustment_entry(self):
        out_inv_1 = self._create_invoice(102, self.tax_10)
        out_inv_2 = self._create_invoice(102, self.tax_10)
        out_inv_3 = self._create_invoice(102, self.tax_10)
        self.assertEqual(out_inv_1.amount_tax, 10)
        self.assertEqual(out_inv_2.amount_tax, 10)
        self.assertEqual(out_inv_3.amount_tax, 10)
        invoices = out_inv_1 + out_inv_2 + out_inv_3
        action = invoices.action_create_billing()
        billing = self.env["account.billing"].browse(action["res_id"])
        self.assertEqual(billing.state, "draft")
        billing.with_company(self.company).validate_billing()
        billing_tax_amount = self._get_billing_tax_amount(billing)
        # The total tax amount should be 31 (306 * 0.1)
        self.assertEqual(abs(billing_tax_amount), 31)
        tax_adj_entry = billing.tax_adjustment_entry_id
        # Since the total tax amount of the billing (31) is different from the total tax
        # amount of the invoices (30), a tax adjustment entry should be created.
        self.assertTrue(tax_adj_entry)
        self.assertEqual(tax_adj_entry.amount_total_signed, 1)
        billing.action_cancel()
        self.assertTrue(tax_adj_entry.state, "cancel")
        self.assertFalse(billing.tax_adjustment_entry_id)
        # Add a credit note to the billing
        out_ref = self._create_invoice(102, self.tax_10, "out_refund")
        self.assertEqual(out_ref.amount_tax, 10)
        billing.action_cancel_draft()
        line_vals = {
            "move_id": out_ref.id,
            "amount_total": -out_ref.amount_total,
            "amount_residual": -out_ref.amount_residual,
        }
        billing.write({"billing_line_ids": [Command.create(line_vals)]})
        self.assertIn(out_ref, billing.billing_line_ids.move_id)
        billing.with_company(self.company).validate_billing()
        billing_tax_amount = self._get_billing_tax_amount(billing)
        # The total tax amount should be 20 (204 * 0.1)
        self.assertEqual(abs(billing_tax_amount), 20)
        self.assertFalse(billing.tax_adjustment_entry_id)
