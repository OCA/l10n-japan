# Copyright 2025 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class ReportPaperformat(models.Model):
    _inherit = "report.paperformat"

    apply_alternative_layout = fields.Boolean(
        help="If selected, the alternative layout will be applied in the printed "
        "report.",
    )
    show_address_in_header = fields.Boolean(
        compute="_compute_show_address_in_header",
        help="If selected, the report header will be shown on every page of the "
        "report output.",
        readonly=False,
        store=True,
    )

    @api.depends("apply_alternative_layout")
    def _compute_show_address_in_header(self):
        for rec in self:
            if rec.apply_alternative_layout:
                continue
            rec.show_address_in_header = False
