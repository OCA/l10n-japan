# Copyright 2025 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    is_not_for_billing = fields.Boolean(
        help="If selected, the invoice is excluded from the billing process.",
    )
    # TODO: This field should be moved to account_billing module.
    billing_line_ids = fields.One2many(
        comodel_name="account.billing.line",
        inverse_name="move_id",
        string="Billing Lines",
    )
    billing_id = fields.Many2one(
        comodel_name="account.billing",
        compute="_compute_billing_id",
        store=True,
    )

    @api.depends("billing_line_ids", "billing_line_ids.billing_id.state")
    def _compute_billing_id(self):
        for move in self:
            valid_billings = move.billing_line_ids.mapped("billing_id").filtered(
                lambda b: b.state != "cancel"
            )
            move.billing_id = valid_billings[:1]

    def _get_partner_bank(self):
        partner_banks = self.mapped("partner_bank_id")
        if len(partner_banks) > 1:
            raise UserError(_("Please select invoices with the same recipient bank."))
        return partner_banks

    def action_create_billing(self):
        self._get_partner_bank()
        return super().action_create_billing()
