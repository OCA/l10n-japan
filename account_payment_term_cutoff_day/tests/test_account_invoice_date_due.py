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
        # There should be a default line
        cls.payment_term_line = cls.payment_term.line_ids
        cls.payment_term_line = cls.payment_term.line_ids
        cls.payment_term_line.has_cutoff_day = True
        cls.payment_term_line.months = 1
        cls.payment_term_line.cutoff_day = 20

    def _create_invoice(self, invoice_date):
        return self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.env.ref("base.res_partner_1").id,
                "invoice_date": invoice_date,
                "invoice_payment_term_id": self.payment_term.id,
            }
        )

    def test_due_date_before_cutoff_day(self):
        """Test if due date remains unchanged when invoice date is before or equal to
        cutoff_day
        """
        computed_due_date = self.payment_term_line._get_due_date(date(2024, 2, 20))
        self.assertEqual(computed_due_date, date(2024, 3, 31))

    def test_due_date_after_cutoff_day(self):
        """Test if due date is shifted by +1 month when invoice date
        is after cutoff_day
        """
        computed_due_date = self.payment_term_line._get_due_date(date(2024, 2, 21))
        self.assertEqual(computed_due_date, date(2024, 4, 30))

    def test_due_date_after_cutoff_day_with_31_days(self):
        """Test if due date is shifted by +1 month and the following month has 31 days
        when invoice date is after cutoff_day
        """
        computed_due_date = self.payment_term_line._get_due_date(date(2025, 1, 31))
        self.assertEqual(computed_due_date, date(2025, 3, 31))

    def test_due_date_no_cutoff_day(self):
        """Test if due date remains unchanged when has_cutoff_day is False"""
        self.payment_term_line.has_cutoff_day = False
        computed_due_date = self.payment_term_line._get_due_date(date(2024, 2, 21))
        self.assertEqual(
            computed_due_date,
            date(2024, 2, 21),
            "Due date should not change when has_cutoff_day is False.",
        )

    def test_invoice_cutoff_date(self):
        inv = self._create_invoice(date(2025, 9, 15))
        self.assertEqual(inv.cutoff_date, date(2025, 9, 20))
        inv.invoice_date = date(2025, 9, 21)
        self.assertEqual(inv.cutoff_date, date(2025, 10, 20))
        inv.invoice_payment_term_id = False
        self.assertEqual(inv.cutoff_date, date(2025, 9, 21))
