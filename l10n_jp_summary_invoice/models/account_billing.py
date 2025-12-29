# Copyright 2024-2025 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError


class AccountBilling(models.Model):
    _inherit = "account.billing"

    # Just changing the default value
    threshold_date_type = fields.Selection(default="invoice_date")
    date_due = fields.Date(
        compute="_compute_billing_date_due",
        store=True,
        readonly=False,
        index=True,
        copy=False,
    )
    tax_totals = fields.Json(
        string="Billing Totals",
        compute="_compute_tax_totals",
        store=True,
        exportable=False,
    )
    amount_untaxed = fields.Monetary(
        string="Untaxed Amount",
        compute="_compute_tax_totals",
        store=True,
    )
    amount_tax = fields.Monetary(
        string="Tax Amount",
        compute="_compute_tax_totals",
        store=True,
    )
    amount_total = fields.Monetary(
        string="Total Amount",
        compute="_compute_tax_totals",
        store=True,
    )
    tax_adjustment_entry_id = fields.Many2one("account.move")
    company_partner_id = fields.Many2one(
        related="company_id.partner_id", string="Company Partner", store=True
    )
    remit_to_bank_id = fields.Many2one(
        "res.partner.bank",
        "Remit-to Bank",
        domain="[('partner_id', '=', company_partner_id)]",
        help="If not specified, the first bank account linked to the company will show "
        "in the report.",
    )

    @api.constrains("state", "billing_line_ids")
    def _check_account_move_billability(self):
        for rec in self:
            invoices = rec.billing_line_ids.move_id
            invoice_not_for_billing = invoices.filtered(
                lambda x: len(x.billing_ids.filtered(lambda x: x.state != "cancel")) > 1
                or x.is_not_for_billing
            )[:1]
            if invoice_not_for_billing:
                raise ValidationError(
                    _(
                        "The invoice %s should not be included in this "
                        "summary invoice.",
                        invoice_not_for_billing.name,
                    )
                )

    @api.constrains("remit_to_bank_id", "billing_line_ids")
    def _check_remit_to_bank_consistency(self):
        for rec in self:
            invoices = rec.billing_line_ids.move_id
            partner_bank = invoices._get_partner_bank()
            if (
                rec.remit_to_bank_id
                and partner_bank
                and rec.remit_to_bank_id != partner_bank
            ):
                raise ValidationError(
                    _(
                        "The remit-to bank of the billing is inconsistent with the "
                        "one on the invoices.",
                    )
                )

    @api.depends("billing_line_ids")
    def _compute_billing_date_due(self):
        for billing in self:
            if not billing.billing_line_ids:
                continue
            billing.date_due = max(
                move.invoice_date_due for move in billing.billing_line_ids.move_id
            )

    @api.depends("billing_line_ids", "partner_id", "currency_id")
    def _compute_tax_totals(self):
        """Compute `tax_totals` by building an in-memory draft invoice that reuses all
        the invoice lines referenced by the billing lines, and then delegating the tax
        calculation to Odoo's standard `account.move._compute_tax_totals()`.
        """
        for bill in self:
            bill.tax_totals = self.env["account.tax"]._get_tax_totals_summary(
                base_lines=[],
                currency=bill.currency_id or bill.company_id.currency_id,
                company=bill.company_id,
            )
            bill.amount_untaxed = 0.0
            bill.amount_tax = 0.0
            bill.amount_total = 0.0
            src_moves = bill.billing_line_ids.move_id
            if not src_moves:
                continue
            move_type = "out_invoice"
            if src_moves.filtered(lambda m: m.move_type in ["in_invoice", "in_refund"]):
                move_type = "in_invoice"
            src_lines = src_moves.invoice_line_ids
            cmd_lines = []
            for src_line in src_lines:
                vals = src_line.copy_data()[0]
                vals["quantity"] *= -src_line.move_id.direction_sign
                cmd_lines.append(Command.create(vals))
            # Build a transient invoice holding those lines
            dummy_move = self.env["account.move"].new(
                {
                    "move_type": move_type,
                    "company_id": bill.company_id.id,
                    "currency_id": bill.currency_id.id,
                    "partner_id": bill.partner_id.id,
                    "invoice_line_ids": cmd_lines,
                }
            )
            dummy_move._compute_tax_totals()
            bill.tax_totals = dummy_move.tax_totals
            if bill.tax_totals:
                bill.amount_untaxed = bill.tax_totals.get("base_amount_currency", 0.0)
                bill.amount_total = bill.tax_totals.get("total_amount_currency", 0.0)
                bill.amount_tax = bill.amount_total - bill.amount_untaxed

    def _update_remit_to_bank_id(self):
        for rec in self:
            if not rec.remit_to_bank_id:
                rec.remit_to_bank_id = rec.billing_line_ids[:1].move_id.partner_bank_id

    @api.model_create_multi
    def create(self, vals_list):
        billings = super().create(vals_list)
        billings._update_remit_to_bank_id()
        return billings

    def compute_lines(self):
        res = super().compute_lines()
        self._update_remit_to_bank_id()
        return res

    def _get_moves(self, date, types=False):
        moves = super()._get_moves(date, types=types)
        if self.remit_to_bank_id:
            moves = moves.filtered(
                lambda x: x.partner_bank_id == self.remit_to_bank_id
                or not x.partner_bank_id
            )
        # Prevent the billing from adding already billed invoices
        moves -= moves.filtered(
            lambda x: x.billing_ids.filtered(lambda x: x.state != "cancel")
            or x.is_not_for_billing
        )
        return moves

    def _get_tax_amount_groups_from_invoices(self):
        """Get the actual tax amounts per tax based on the invoice lines
        associated with billing lines.
        """
        self.ensure_one()
        tax_amount_groups = self.env["account.move.line"].read_group(
            domain=[
                ("move_id", "in", self.billing_line_ids.move_id.ids),
                "|",
                ("display_type", "=", "tax"),
                "&",
                ("display_type", "=", "rounding"),
                ("tax_repartition_line_id", "!=", False),
            ],
            fields=["tax_group_id", "balance"],
            groupby=["tax_group_id"],
        )
        return tax_amount_groups

    def _get_inv_line_account_id(self):
        self.ensure_one()
        return self.env["account.account"]._get_most_frequent_account_for_partner(
            company_id=self.company_id.id,
            partner_id=self.partner_id.id,
            move_type="out_invoice",
        )

    def validate_billing(self):
        res = super().validate_billing()
        # Tax journal entry will be created only for customer invoice billings.
        for rec in self.filtered(lambda x: x.bill_type == "out_invoice"):
            tax_totals = rec.tax_totals
            if not tax_totals:
                continue
            tax_group_amount_dict = {}
            for subtotal in tax_totals.get("subtotals", []):
                for group in subtotal.get("tax_groups", []):
                    tax_group_id = group.get("id")
                    tax_amount = group.get("tax_amount", 0.0)
                    tax_group_amount_dict[tax_group_id] = tax_amount * -1
            tax_amount_groups_invoices = rec._get_tax_amount_groups_from_invoices()
            tax_group_diff_dict = {}
            for tax_amount_group in tax_amount_groups_invoices:
                tax_group_id = tax_amount_group["tax_group_id"][0]
                tax_amount_invoices = tax_amount_group["balance"]
                tax_amount_bill = tax_group_amount_dict.get(tax_group_id, 0)
                tax_diff = tax_amount_invoices - tax_amount_bill
                if tax_diff:
                    tax_group_diff_dict[tax_group_id] = tax_diff
            if not tax_group_diff_dict:
                continue
            invoice_vals = {
                "move_type": "out_invoice",
                "partner_id": rec.partner_id.id,
                "date": rec.date,
                "invoice_origin": rec.name,
                "ref": f"Tax adjustment for {rec.name}",
                "is_not_for_billing": True,
                "line_ids": [],
            }
            inv_line_account_id = rec._get_inv_line_account_id()
            diff_balance = 0.0
            for tax_group_id, diff in tax_group_diff_dict.items():
                tax_group = self.env["account.tax.group"].browse(tax_group_id)
                adjustment_tax = tax_group._get_adjustment_tax()
                invoice_vals["line_ids"].append(
                    Command.create(
                        {
                            "name": f"Tax adjustment for {tax_group.name}",
                            "account_id": inv_line_account_id,
                            "quantity": 1,
                            "price_unit": diff,
                            "tax_ids": [Command.set(adjustment_tax.ids)],
                        },
                    )
                )
                diff_balance += diff
            adjustment_move = self.env["account.move"].create(invoice_vals)
            if diff_balance < 0:
                adjustment_move.action_switch_move_type()
            adjustment_move.action_post()
            rec.tax_adjustment_entry_id = adjustment_move
        return res

    def action_cancel(self):
        res = super().action_cancel()
        for rec in self:
            rec.tax_adjustment_entry_id.button_draft()
            rec.tax_adjustment_entry_id.button_cancel()
            rec.tax_adjustment_entry_id = False
        return res
