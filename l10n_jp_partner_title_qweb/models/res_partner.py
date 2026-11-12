# Copyright 2025 Quartile (https://www.quartile.co)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    honorific_title = fields.Char()
    honorific_title_position = fields.Selection(
        [("before", "Before Name"), ("after", "After Name")],
        default="after",
    )
