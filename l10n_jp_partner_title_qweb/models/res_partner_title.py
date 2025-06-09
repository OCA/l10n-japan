# Copyright 2018 Quartile
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class ResPartnerTitle(models.Model):
    _inherit = "res.partner.title"

    display_position = fields.Selection(
        [("before", "Before Name"), ("after", "After Name")],
    )
