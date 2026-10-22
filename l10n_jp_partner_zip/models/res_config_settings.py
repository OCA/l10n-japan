# Copyright 2026 Quartile (https://www.quartile.co)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_jp_zip_format = fields.Selection(
        [("hyphen", "With hyphen (810-0041)"), ("digits", "Digits only (8100041)")],
        string="Japanese Postcode Format",
        default="hyphen",
        required=True,
        config_parameter="l10n_jp_partner_zip.format",
        help="Applies to postcodes written from now on. Postcodes already stored "
        "keep their format.",
    )
