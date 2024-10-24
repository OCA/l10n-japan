# Copyright 2024-2025 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class Report(models.Model):
    _inherit = "ir.actions.report"

    apply_alternative_layout = fields.Boolean(
        help="If selected, the alternative layout will be applied in the printed "
        "report.",
    )
    show_commercial_partner = fields.Boolean(
        help="If selected, the commercial partner of the document partner will show "
        "in the report output (instead of the document partner)."
    )
    show_remit_to_bank = fields.Boolean(
        "Show Remit-to Bank",
        help="If selected, remit-to bank account will show in the report output.",
    )

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        report = self._get_report(report_ref)
        if report.apply_alternative_layout:
            self = self.with_context(apply_alternative_layout=True)
        return super()._render_qweb_pdf(report_ref, res_ids, data)

    def _get_partner(self, partner):
        self.ensure_one()
        if self.show_commercial_partner:
            return partner.commercial_partner_id
        return partner

    def _get_remit_to_bank(self, record):
        self.ensure_one()
        if not self.show_remit_to_bank:
            return False
        if "company_id" not in record._fields:
            return False
        company = record.company_id
        if not company:
            return False
        return company.bank_ids[:1]
