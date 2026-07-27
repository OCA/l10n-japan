# Copyright 2025 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    delivery_note_narration = fields.Html("Delivery Note Comment")
    show_delivery_note_narration = fields.Boolean(
        compute="_compute_show_delivery_note_narration"
    )

    @api.depends("company_id.use_delivery_note_narration")
    def _compute_show_delivery_note_narration(self):
        for move in self:
            move.show_delivery_note_narration = (
                move.company_id.use_delivery_note_narration
            )

    def get_report_document_title(self, is_delivery_note=False):
        self.ensure_one()
        company = self.company_id
        if self.move_type == "out_invoice":
            if is_delivery_note:
                return company.invoice_report_delivery_note_title or ""
            return company.invoice_report_title or ""
        elif self.move_type == "out_refund":
            if is_delivery_note:
                return company.invoice_report_return_slip_title or ""
            return company.invoice_report_credit_note_title or ""
        return ""
