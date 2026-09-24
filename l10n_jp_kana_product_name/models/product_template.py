# Copyright 2026 Quartile (https://www.quartile.co)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import models


class ProductTemplate(models.Model):
    _name = "product.template"
    _inherit = ["product.template", "kana.mixin", "name.kana.mixin"]
