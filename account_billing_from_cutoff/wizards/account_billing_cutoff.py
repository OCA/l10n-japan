# Copyright 2025 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from collections import defaultdict

from odoo import fields, models


class AccountBillingCutoff(models.TransientModel):
    _name = "wiz.account.billing.cutoff"
    _description = "Account Billing From Cutoff"

    cutoff_date = fields.Date(required=True, default=fields.Date.context_today)
    bill_type = fields.Selection(
        selection=[("out_invoice", "Customer Invoice"), ("in_invoice", "Vendor Bill")],
        readonly=True,
    )

    def _allowed_move_types(self):
        if self.bill_type == "out_invoice":
            return ["out_invoice", "out_refund", "out_receipt"]
        return ["in_invoice", "in_refund", "in_receipt"]

    def _search_moves_domain(self):
        billed_move_ids = (
            self.env["account.billing.line"]
            .search(
                [
                    ("billing_id.state", "in", ["draft", "billed"]),
                ]
            )
            .mapped("move_id")
            .ids
        )
        return [
            ("id", "not in", billed_move_ids),
            ("is_not_for_billing", "=", False),
            ("company_id", "=", self.env.company.id),
            ("state", "=", "posted"),
            ("payment_state", "not in", ["paid", "reversed", "invoicing_legacy"]),
            ("move_type", "in", self._allowed_move_types()),
            ("cutoff_date", "<=", self.cutoff_date),
        ]

    def action_create_billings(self):
        moves = self.env["account.move"].search(self._search_moves_domain())
        if not moves:
            return {"type": "ir.actions.act_window_close"}
        groups = defaultdict(lambda: self.env["account.move"])
        for m in moves:
            key = (m.partner_id.id, m.currency_id.id)
            groups[key] |= m
        billings = self.env["account.billing"]
        for (partner_id, currency_id), recs in groups.items():
            partner = self.env["res.partner"].browse(partner_id)
            existing_billing = self.env["account.billing"].search(
                [
                    ("partner_id", "=", partner_id),
                    ("currency_id", "=", currency_id),
                    ("bill_type", "=", recs._get_billing_type()),
                    ("state", "=", "draft"),
                ],
                limit=1,
            )
            if existing_billing:
                billing_line_dict = existing_billing._get_billing_line_dict(recs)
                existing_billing.billing_line_ids.create(billing_line_dict)
                billings |= existing_billing
            else:
                billings |= recs._create_billing(partner)
        return {
            "type": "ir.actions.act_window",
            "name": "Billings",
            "res_model": "account.billing",
            "view_mode": "tree,form",
            "domain": [("id", "in", billings.ids)],
            "target": "current",
        }
