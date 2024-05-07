# Copyright 2024 Quartile Limited
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    duplicate_corp_number_behavior = fields.Selection(
        [("error", "Error"), ("warning", "Warning")],
        help="Define the behavior when a duplicate corporate number is detected: "
        "'Error' will block the operation, "
        "'Warning' will allow but notify.",
    )

    error_message = fields.Text(
        string="Error Message for Duplicate Corp Number",
        default="A partner with this corporate number already exists.",
        help="Custom error message to display when a duplicate corporate number "
        "is detected and behavior is set to 'Error'.",
    )

    warning_message = fields.Text(
        string="Warning Message for Duplicate Corp Number",
        default="Warning: A partner with this corporate number already exists.",
        help="Custom warning message to display when a duplicate corporate number "
        "is detected and behavior is set to 'Warning'.",
    )
