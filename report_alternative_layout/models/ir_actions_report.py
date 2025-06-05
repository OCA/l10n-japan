# Copyright 2024-2025 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.tools import format_date


class Report(models.Model):
    _inherit = "ir.actions.report"

    show_commercial_partner = fields.Boolean(
        help="If selected, the commercial partner of the document partner will show "
        "in the report output (instead of the document partner)."
    )
    show_remit_to_bank = fields.Boolean(
        "Show Remit-to Bank",
        help="If selected, remit-to bank account will show in the report output.",
    )
    show_document_number = fields.Boolean(
        "Show Document Number in Header",
        help="If selected, the document number will show in the report header.",
    )
    date_field_id = fields.Many2one(
        "ir.model.fields",
        domain="[('model','=', model), ('ttype', 'in', ('date', 'datetime'))]",
        string="Date Field to Show in Header",
        help="If set, the report will show the value of this field in the header as "
        "the date of the document.",
    )
    date_field_label = fields.Char(
        translate=True,
        help="Label for the date field in the report header. If not set, the field's "
        "description will be used.",
    )
    apply_alternative_layout = fields.Boolean(
        related="paperformat_id.apply_alternative_layout"
    )

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        report = self._get_report(report_ref)
        self = self.with_context(
            apply_alternative_layout=report.paperformat_id.apply_alternative_layout,
            show_address_in_header=report.paperformat_id.show_address_in_header,
        )
        return super()._render_qweb_pdf(report_ref, res_ids, data)

    def _get_report_partner(self, record):
        self.ensure_one()
        if hasattr(record, "partner_id"):
            if self.show_commercial_partner:
                return record.partner_id.commercial_partner_id
            return record.partner_id
        return self.env.user.partner_id

    @api.model
    def _get_bank_field_name(self, record):
        """Get the name of the field that links the record to the bank account.

        We assume that there is usually just one field in the model with many2one
        relationship to res.partner.bank. In case of an exception, this method should be
        extended in the specific model to identify the correct field.
        """
        return next(
            (
                field.name
                for field in record._fields.values()
                if field.type == "many2one" and field.comodel_name == "res.partner.bank"
            ),
            None,
        )

    def _get_remit_to_bank(self, record):
        self.ensure_one()
        if not self.show_remit_to_bank:
            return False
        bank_field_name = self._get_bank_field_name(record)
        if bank_field_name:
            return getattr(record, bank_field_name)
        if "company_id" not in record._fields:
            return False
        company = record.company_id
        if not company:
            return False
        return company.bank_ids[:1]

    def _get_date_value(self, record):
        self.ensure_one()
        if not self.date_field_id:
            return None
        value = record[self.date_field_id.name]
        if not value:
            return None
        try:
            return format_date(self.env, value)
        except (TypeError, ValueError):
            return None

    def _get_date_field_label(self):
        self.ensure_one()
        return self.date_field_label or self.date_field_id.field_description or ""
