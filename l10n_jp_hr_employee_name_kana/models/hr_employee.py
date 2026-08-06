# Copyright 2026 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class HrEmployee(models.Model):
    _name = "hr.employee"
    _inherit = ["hr.employee", "name.kana.mixin"]
