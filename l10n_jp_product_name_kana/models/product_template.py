# Copyright 2026 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class ProductTemplate(models.Model):
    _name = "product.template"
    _inherit = ["product.template", "name.kana.mixin"]
