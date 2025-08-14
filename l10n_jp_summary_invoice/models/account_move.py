# Copyright 2025 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    is_not_for_billing = fields.Boolean(
        help="If selected, the invoice is excluded from the billing process.",
    )

    def _get_partner_bank(self):
        partner_banks = self.mapped("partner_bank_id")
        if len(partner_banks) > 1:
            raise UserError(_("Please select invoices with the same recipient bank."))
        return partner_banks

    def action_create_billing(self):
        self._get_partner_bank()
        return super().action_create_billing()
