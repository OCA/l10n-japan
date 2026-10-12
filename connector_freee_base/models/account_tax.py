# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, fields, models


class AccountTax(models.Model):
    _inherit = "account.tax"

    freee_tax_code = fields.Integer(
        string="freee Tax Code",
        help="freee ``tax_code`` to set on each detail line "
        "(e.g. ``21`` for the standard 10% sales rate, "
        "``24`` for the 8% reduced sales rate). "
        "freee's deals API rejects the value unless it is an integer.",
    )
    freee_tax_name = fields.Char(
        string="freee Tax Name",
        help="Display name of the matching freee tax, captured when "
        "the code is set via the picker wizard. Display-only — only "
        "the code gets sent to the API.",
    )

    def action_open_freee_tax_code_wizard(self):
        """Open the wizard to pick the matching freee tax code."""
        self.ensure_one()
        wizard = self.env["freee.tax.code.fetch.wizard"].create({"tax_id": self.id})
        return {
            "type": "ir.actions.act_window",
            "name": _("Map freee Tax Code"),
            "res_model": "freee.tax.code.fetch.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_clear_freee_tax_code(self):
        """Unmap the freee tax code. Invoices using this tax then fail
        to export (a tax code is required per detail row — see
        ``freee.export.mapper._pick_freee_tax``) until one is
        mapped again."""
        self.write(
            {
                "freee_tax_code": False,
                "freee_tax_name": False,
            }
        )
