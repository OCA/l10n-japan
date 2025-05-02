# Copyright 2025 Quartile
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from dateutil.relativedelta import relativedelta

from odoo import fields, models


class AccountPaymentTermLine(models.Model):
    _inherit = "account.payment.term.line"

    cutoff_day = fields.Integer(
        default=31,
        help="Specify the cutoff day of the month for adjusting invoice due dates."
        "For example, if you set this field to 20, any invoice dated on the 21st or later "
        "will have its due date moved to the following month."
        "Setting 0 is treated the same as having no cutoff day, which in practice is the "
        "same as setting 31.",
    )

    def _get_due_date(self, date_ref):
        if date_ref and self.end_month and self.cutoff_day:
            date_dt = fields.Date.to_date(date_ref)
            if date_dt.day > self.cutoff_day:
                date_ref += relativedelta(months=1)
        return super()._get_due_date(date_ref)
