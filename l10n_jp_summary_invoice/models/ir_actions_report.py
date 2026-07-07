# Copyright 2026 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import models


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        result = super()._render_qweb_pdf(report_ref, res_ids, data)
        report = self._get_report(report_ref)
        if report.model == "account.billing" and res_ids:
            if isinstance(res_ids, int):
                res_ids = [res_ids]
            billings = self.env["account.billing"].sudo().browse(res_ids)
            billings.filtered("name").write({"is_billing_sent": True})
        return result
