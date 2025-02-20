# Copyright 2025 Quartile
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import date

from odoo.tests.common import TransactionCase


class TestPaymentTermCutoffDate(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.payment_term = cls.env["account.payment.term"].create(
            {"name": "Test Payment Term"}
        )
        cls.payment_term_line = cls.env["account.payment.term.line"].create(
            {
                "payment_id": cls.payment_term.id,
                "value": "balance",
                "months": 1,
                "end_month": True,
                "cutoff_day": 20,
            }
        )

    def test_due_date_before_cutoff_day(self):
        """Test if due date remains unchanged when invoice date is
        before or equal to cutoff_day"""
        invoice_date = date(2024, 2, 20)
        expected_due_date = date(2024, 3, 31)
        computed_due_date = self.payment_term_line._get_due_date(invoice_date)
        self.assertEqual(
            computed_due_date,
            expected_due_date,
        )

    def test_due_date_after_cutoff_day(self):
        """Test if due date is shifted by +1 month
        when invoice date is after cutoff_day"""
        invoice_date = date(2024, 2, 21)
        expected_due_date = date(2024, 4, 30)
        computed_due_date = self.payment_term_line._get_due_date(invoice_date)
        self.assertEqual(
            computed_due_date,
            expected_due_date,
        )

    def test_due_date_no_cutoff_day(self):
        """Test if due date remains unchanged when cutoff_day is not set"""
        self.payment_term_line.cutoff_day = False
        invoice_date = date(2024, 2, 21)
        expected_due_date = date(2024, 3, 31)
        computed_due_date = self.payment_term_line._get_due_date(invoice_date)
        self.assertEqual(
            computed_due_date,
            expected_due_date,
            "Due date should not change when cutoff_day is not set.",
        )
