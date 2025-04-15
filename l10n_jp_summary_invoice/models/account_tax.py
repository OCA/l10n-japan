# Copyright 2025 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class AccountTax(models.Model):
    _inherit = "account.tax"

    rounding_adjustment = fields.Boolean(
        readonly=True,
        help="If selected, it means that this tax was auto-generated for rounding "
        "adjustment purposes.",
    )
