# Copyright 2025 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    show_sale_order_number = fields.Boolean(
        "Show Sales Order Number",
        help="If enabled, the sales order number will be displayed in the summary "
        "invoice report lines.",
    )
    show_sale_order_reference = fields.Boolean(
        "Show Sales Order Reference",
        help="If enabled, the sales order reference will be displayed in the summary "
        "invoice report lines.",
    )
