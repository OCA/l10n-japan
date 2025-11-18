# Copyright 2025 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    show_order_partner = fields.Boolean(
        related="company_id.show_order_partner", readonly=False
    )
    show_order_shipping_partner = fields.Boolean(
        related="company_id.show_order_shipping_partner", readonly=False
    )
