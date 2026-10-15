# Copyright 2026 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_not_for_billing = fields.Boolean(
        help="If enabled, invoices for this partner will be excluded from "
        "the billing process by default.",
    )
