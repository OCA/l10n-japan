# Copyright 2025 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    invoice_report_delivery_note_title = fields.Char(
        default=lambda self: _("Delivery Note"), translate=True
    )
    invoice_report_return_slip_title = fields.Char(
        default=lambda self: _("Return Slip"), translate=True
    )
    invoice_report_title = fields.Char(translate=True)
    invoice_report_credit_note_title = fields.Char(translate=True)
    use_delivery_note_narration = fields.Boolean(
        string="Use Delivery Note Comment",
        default=True,
    )
    hide_narration_on_delivery_note = fields.Boolean(
        string="Hide Narration on Delivery Note",
        default=True,
    )
