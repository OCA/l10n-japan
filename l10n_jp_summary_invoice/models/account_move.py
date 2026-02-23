# Copyright 2025 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    is_not_for_billing = fields.Boolean(
        compute="_compute_is_not_for_billing",
        store=True,
        readonly=False,
        help="If selected, the invoice is excluded from the billing process.",
    )

    @api.depends("partner_id")
    def _compute_is_not_for_billing(self):
        for move in self:
            # Intentionally not using move.commercial_partner_id to allow more granular
            # control
            move.is_not_for_billing = move.partner_id.is_not_for_billing

    def _get_partner_bank(self):
        partner_banks = self.mapped("partner_bank_id")
        if len(partner_banks) > 1:
            raise UserError(_("Please select invoices with the same recipient bank."))
        return partner_banks

    def action_create_billing(self):
        self._get_partner_bank()
        return super().action_create_billing()

    # TODO: Propose to move this to account_billing?
    def button_draft(self):
        for rec in self:
            if rec.billing_ids.filtered(lambda x: x.state != "cancel"):
                raise UserError(
                    _("You cannot reset to draft an invoice that has been billed.")
                )
        return super().button_draft()
