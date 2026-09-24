# Copyright 2026 Quartile (https://www.quartile.co)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models


class HrEmployeePublic(models.Model):
    _name = "hr.employee.public"
    _inherit = ["hr.employee.public", "kana.mixin", "name.kana.mixin"]

    # Readonly like the other fields this SQL view takes from hr.employee.
    name_kana = fields.Char(readonly=True)

    @api.model
    def _get_kana_format(self):
        """Follow the employee setting: the view exposes what hr.employee stores,
        so a setting of its own could disagree and make searches match nothing.
        """
        return self.env["hr.employee"]._get_kana_format()
