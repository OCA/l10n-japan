# Copyright 2026 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class HrEmployeePublic(models.Model):
    _name = "hr.employee.public"
    _inherit = ["hr.employee.public", "name.kana.mixin"]

    name_kana = fields.Char(readonly=True)

    @api.model
    def _get_kana_format(self):
        """Follow the employee setting rather than resolving one of our own.

        This model is a read-only SQL view: the reading it exposes is the one
        stored on hr.employee, so a search term has to be normalized to that
        format. A setting of its own could disagree, and searching the employee
        directory would then match nothing.
        """
        return self.env["hr.employee"]._get_kana_format()
