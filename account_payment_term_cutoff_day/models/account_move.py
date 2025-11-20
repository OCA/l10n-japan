# Copyright 2025 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    cutoff_date = fields.Date(compute="_compute_cutoff_date", store=True)

    @api.depends("invoice_date", "invoice_payment_term_id")
    def _compute_cutoff_date(self):
        for move in self:
            if not move.invoice_date:
                move.cutoff_date = False
                continue
            term_lines = move.invoice_payment_term_id.line_ids
            if not term_lines or len(term_lines) > 1:
                move.cutoff_date = move.invoice_date
                continue
            move.cutoff_date = term_lines._get_cutoff_date(move.invoice_date)
