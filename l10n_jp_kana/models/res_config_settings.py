# Copyright 2026 Quartile (https://www.quartile.co)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models

from .kana_mixin import (
    DEFAULT_KANA_FORMAT,
    KANA_FORMAT_PARAM,
    KANA_FORMAT_SELECTION,
)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    kana_format = fields.Selection(
        selection=KANA_FORMAT_SELECTION,
        config_parameter=KANA_FORMAT_PARAM,
        default=DEFAULT_KANA_FORMAT,
    )
