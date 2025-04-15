# Copyright 2025 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    summary_invoice_remark = fields.Html(
        translate=True,
        default="下記の通り御請求申し上げます。",
        help="Content here will be displayed in the summary invoice report.",
    )
    show_sale_order_number = fields.Boolean(
        "Show Sales Order Number",
        help="If enabled, the sales order number will be displayed in the summary "
        "invoice report lines.",
    )
    show_invoice_narration = fields.Boolean(
        default=True,
        help="If enabled, the invoice narration will be displayed in the summary "
        "invoice report.",
    )
    show_invoice_total_amount = fields.Boolean(
        default=True,
        help="If enabled, the invoice total amount will be displayed in the summary "
        "invoice report.",
    )
