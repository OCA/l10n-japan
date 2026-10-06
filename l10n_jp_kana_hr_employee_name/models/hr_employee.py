# Copyright 2026 Quartile (https://www.quartile.co)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import models


class HrEmployee(models.Model):
    _name = "hr.employee"
    _inherit = ["hr.employee", "kana.mixin", "name.kana.mixin"]
