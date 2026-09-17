# Copyright 2026 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.fields import Command

from odoo.addons.base.tests.common import BaseCommon


class TestSummaryInvoiceUntaxedUnrounded(BaseCommon):
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
                "code": "testrec",
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
        cls.product = cls.env["product.product"].create({"name": "Test Product"})
        cls.tax_group = cls.env["account.tax.group"].create({"name": "Tax Group"})
        cls.tax_10 = cls.env["account.tax"].create(
            {
                "name": "Test Tax 10%",
                "amount": 10.0,
                "type_tax_use": "sale",
                "company_id": cls.company.id,
                "tax_group_id": cls.tax_group.id,
            }
        )
        cls.env["account.journal"].create(
            {"code": "test", "name": "test", "type": "sale"}
        )
        cls.account_income = cls.env["account.account"].create(
            {"code": "testinc", "name": "income", "account_type": "income"}
        )

    def _create_invoice(self, amount):
        invoice = (
            self.env["account.move"]
            .with_company(self.company)
            .create(
                {
                    "move_type": "out_invoice",
                    "partner_id": self.partner.id,
                    "currency_id": self.company.currency_id.id,
                    "invoice_line_ids": [
                        Command.create(
                            {
                                "product_id": self.product.id,
                                "account_id": self.account_income.id,
                                "quantity": 1,
                                "price_unit": amount,
                                "tax_ids": [Command.set(self.tax_10.ids)],
                            }
                        )
                    ],
                }
            )
        )
        invoice.action_post()
        return invoice

    def test_amount_untaxed_unrounded(self):
        """100.3 JPY line: rounded untaxed is 100, unrounded is 100.3."""
        invoice = self._create_invoice(100.3)
        self.assertEqual(invoice.amount_untaxed, 100)
        self.assertAlmostEqual(invoice.amount_untaxed_unrounded, 100.3, places=2)
        self.assertAlmostEqual(
            invoice.invoice_line_ids.price_subtotal_unrounded, 100.3, places=2
        )

    def test_summary_invoice_report_shows_unrounded(self):
        """The summary invoice report discloses the unrounded subtotals at the
        company's configured digits (2 -> '100.30')."""
        invoices = self._create_invoice(100.3) + self._create_invoice(100.3)
        action = invoices.action_create_billing()
        billing = self.env["account.billing"].browse(action["res_id"])
        billing.with_company(self.company).validate_billing()
        html = (
            self.env["ir.actions.report"]
            ._render_qweb_html(
                "l10n_jp_summary_invoice.report_jp_summary_invoice", billing.ids
            )[0]
            .decode()
        )
        self.assertIn("100.30", html)
