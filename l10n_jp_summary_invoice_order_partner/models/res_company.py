# Copyright 2025 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    show_order_partner = fields.Boolean(
        help="If enabled, the sales order partner will be displayed in the summary "
        "invoice report lines.",
    )
    show_order_shipping_partner = fields.Boolean(
        help="If enabled, the sales order shipping partner will be displayed "
        "in the summary invoice report lines.",
    )
