# Copyright 2025 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.fields import Command
from odoo.tests.common import TransactionCase


class TestAccountMoveDeliveryInvoice(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env["res.partner"].create({"name": "Test Customer"})

    def _create_invoice(self, move_type="out_invoice"):
        return self.env["account.move"].create(
            {
                "move_type": move_type,
                "partner_id": self.partner.id,
                "invoice_line_ids": [
                    Command.create(
                        {"name": "Test Line", "quantity": 1, "price_unit": 100.0}
                    )
                ],
            }
        )

    def test_get_report_document_title_out_invoice(self):
        invoice = self._create_invoice("out_invoice")
        self.company.invoice_report_delivery_note_title = "Custom Delivery Note Title"
        self.company.invoice_report_title = "Custom Invoice Title"
        title = invoice.get_report_document_title(is_delivery_note=True)
        self.assertEqual(title, "Custom Delivery Note Title")
        title = invoice.get_report_document_title(is_delivery_note=False)
        self.assertEqual(title, "Custom Invoice Title")

    def test_get_report_document_title_out_refund(self):
        refund = self._create_invoice("out_refund")
        self.company.invoice_report_return_slip_title = "Custom Return Slip Title"
        self.company.invoice_report_credit_note_title = "Custom Credit Note Title"
        title = refund.get_report_document_title(is_delivery_note=True)
        self.assertEqual(title, "Custom Return Slip Title")
        title = refund.get_report_document_title(is_delivery_note=False)
        self.assertEqual(title, "Custom Credit Note Title")

    def test_get_report_document_title_other_move_types(self):
        vendor_bill = self._create_invoice("in_invoice")
        title = vendor_bill.get_report_document_title()
        # Should be empty for non-customer invoices
        self.assertEqual(title, "")
