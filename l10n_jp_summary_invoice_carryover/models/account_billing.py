# Copyright 2025 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class AccountBilling(models.Model):
    _inherit = "account.billing"

    prev_billing_id = fields.Many2one(
        "account.billing",
        string="Previous Billing",
        compute="_compute_prev_billing_id",
        store=True,
        readonly=False,
        domain="[('id', 'in', prev_billing_candidate_ids)]",
        tracking=True,
    )
    prev_billing_candidate_ids = fields.Many2many(
        "account.billing",
        string="Previous Billing Candidates",
        compute="_compute_prev_billing_candidate_ids",
    )
    use_prev_billed_amount_manual = fields.Boolean(
        string="Use Manual Previous Billed Amount",
        tracking=True,
        copy=False,
    )
    prev_billed_amount_manual = fields.Monetary(
        string="Previous Billed Amount (Manual)",
        tracking=True,
        copy=False,
        help="Manual override for previous billed amount.",
    )
    prev_billed_amount = fields.Monetary(
        string="Previous Billed Amount",
        compute="_compute_carryover_amounts",
        store=True,
        help="Total billed amount from the previous billing.",
    )
    use_payment_amount_manual = fields.Boolean(
        string="Use Manual Payment Amount",
        tracking=True,
        copy=False,
    )
    payment_amount_manual = fields.Monetary(
        string="Payment Amount (Manual)",
        tracking=True,
        copy=False,
        help="Manual override for payment amount.",
    )
    payment_amount = fields.Monetary(
        compute="_compute_carryover_amounts",
        store=True,
        help="Payments received on previous billing invoices.",
    )
    carryover_amount = fields.Monetary(
        compute="_compute_carryover_amounts",
        store=True,
        help="Previous billing amount minus payments.",
    )
    total_billed_amount = fields.Monetary(
        compute="_compute_carryover_amounts",
        store=True,
        recursive=True,
        help="Carryover plus current billed amount.",
    )
    show_carryover_amounts = fields.Boolean(
        compute="_compute_show_carryover_amounts",
        store=True,
        readonly=False,
        help="Whether to show carryover amounts in the summary invoice report.",
    )

    def _get_prev_billing_domain(self):
        self.ensure_one()
        return [
            ("company_id", "=", self.company_id.id),
            (
                "partner_id.commercial_partner_id",
                "=",
                self.partner_id.commercial_partner_id.id,
            ),
            ("bill_type", "=", self.bill_type),
            ("currency_id", "=", self.currency_id.id),
            ("state", "=", "billed"),
            ("date", "<", self.date or fields.Date.today()),
            ("id", "!=", self.id),
        ]

    @api.depends("partner_id", "bill_type", "currency_id", "date", "state")
    def _compute_prev_billing_candidate_ids(self):
        for rec in self:
            rec.prev_billing_candidate_ids = self.search(rec._get_prev_billing_domain())

    @api.depends("partner_id", "bill_type", "currency_id", "date", "state")
    def _compute_prev_billing_id(self):
        for rec in self:
            rec.prev_billing_id = self.search(
                rec._get_prev_billing_domain(),
                order="date desc, id desc",
                limit=1,
            )

    def _get_prev_billed_amount(self):
        self.ensure_one()
        return (
            self.prev_billed_amount_manual
            if self.use_prev_billed_amount_manual
            else self.prev_billed_amount
        )

    def _get_payment_amount(self):
        self.ensure_one()
        return (
            self.payment_amount_manual
            if self.use_payment_amount_manual
            else self.payment_amount
        )

    @api.depends(
        "prev_billing_id",
        "use_prev_billed_amount_manual",
        "prev_billed_amount_manual",
        "use_payment_amount_manual",
        "payment_amount_manual",
        "amount_total",
        "prev_billing_id.total_billed_amount",
        "prev_billing_id.billing_line_ids.amount_residual",
        "prev_billing_id.tax_adjustment_entry_id.amount_residual",
    )
    def _compute_carryover_amounts(self):
        for rec in self:
            rec.prev_billed_amount = 0.0
            rec.payment_amount = 0.0
            rec.carryover_amount = 0.0
            rec.total_billed_amount = rec.amount_total
            prev_billing = rec.prev_billing_id
            if prev_billing:
                rec.prev_billed_amount = prev_billing.total_billed_amount
                current_residual = (
                    sum(line.amount_residual for line in prev_billing.billing_line_ids)
                    + prev_billing.tax_adjustment_entry_id.amount_residual
                )
                rec.payment_amount = rec.prev_billed_amount - current_residual
            prev_billed_amount = rec._get_prev_billed_amount()
            payment_amount = rec._get_payment_amount()
            rec.carryover_amount = prev_billed_amount - payment_amount
            rec.total_billed_amount = rec.carryover_amount + rec.amount_total

    @api.depends("partner_id")
    def _compute_show_carryover_amounts(self):
        for rec in self:
            partner = rec.partner_id.commercial_partner_id
            if partner.show_carryover_amounts == "yes":
                rec.show_carryover_amounts = True
            elif partner.show_carryover_amounts == "no":
                rec.show_carryover_amounts = False
            else:
                rec.show_carryover_amounts = rec.company_id.show_carryover_amounts

    def validate_billing(self):
        for rec in self:
            if not rec.use_prev_billed_amount_manual:
                rec.use_prev_billed_amount_manual = True
                rec.prev_billed_amount_manual = rec.prev_billed_amount
            if not rec.use_payment_amount_manual:
                rec.use_payment_amount_manual = True
                rec.payment_amount_manual = rec.payment_amount
        return super().validate_billing()
