# Copyright 2025 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from dateutil.relativedelta import relativedelta

from odoo import fields, models
from odoo.tools import date_utils


class AccountPaymentTermLine(models.Model):
    _inherit = "account.payment.term.line"

    has_cutoff_day = fields.Boolean(
        help="Indicates if the payment term line has a cutoff day."
    )
    months = fields.Integer(required=True, default=0)
    cutoff_day = fields.Integer(
        help="Specify the cutoff day of the month for adjusting invoice due dates."
        "For example, if you set this field to 20, any invoice dated on the 21st or "
        "later will have its due date moved to the following month."
        "Setting 0 is treated the same as having no cutoff day",
    )

    def _get_cutoff_date(self, date_ref):
        self.ensure_one()
        if not self.has_cutoff_day or not self.cutoff_day:
            return date_ref
        last_dom = date_utils.end_of(date_ref, "month").day
        cutoff_day = min(self.cutoff_day, last_dom)
        date_cutoff = date_ref.replace(day=cutoff_day)
        if date_ref.day > self.cutoff_day:
            date_cutoff += relativedelta(months=1)
        return date_cutoff

    def _get_due_date(self, date_ref):
        self.ensure_one()
        if date_ref and self.has_cutoff_day:
            self.delay_type = "days_after_end_of_month"
            date_ref = self._get_cutoff_date(date_ref)
            date_ref += relativedelta(months=self.months)
        return super()._get_due_date(date_ref)
