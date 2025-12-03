# Copyright 2025 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    invoice_report_delivery_note_title = fields.Char(
        related="company_id.invoice_report_delivery_note_title",
        readonly=False,
    )
    invoice_report_return_slip_title = fields.Char(
        related="company_id.invoice_report_return_slip_title",
        readonly=False,
    )
    invoice_report_title = fields.Char(
        related="company_id.invoice_report_title",
        readonly=False,
    )
    invoice_report_credit_note_title = fields.Char(
        related="company_id.invoice_report_credit_note_title",
        readonly=False,
    )
    use_delivery_note_narration = fields.Boolean(
        related="company_id.use_delivery_note_narration",
        readonly=False,
    )
    hide_narration_on_delivery_note = fields.Boolean(
        related="company_id.hide_narration_on_delivery_note",
        readonly=False,
    )
