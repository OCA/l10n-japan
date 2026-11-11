# Copyright 2025 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    show_carryover_amounts = fields.Selection(
        selection=[
            ("default", "Use Company Default"),
            ("yes", "Yes"),
            ("no", "No"),
        ],
        default="default",
        help="Whether to show carryover amounts in the summary invoice report. "
        "If set to 'Use Company Default', the company setting will be used.",
    )
