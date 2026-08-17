# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, fields, models


class AccountAnalyticAccount(models.Model):
    _inherit = "account.analytic.account"

    freee_section_id = fields.Integer(
        string="freee Section ID",
        help="ID of the matching ``section`` on freee. Stored "
        "here so exporters can populate ``details[].section_id`` in "
        "the deal payload without round-tripping the API on every "
        "push.",
    )
    freee_section_name = fields.Char(
        string="freee Section Name",
        help="Name of the matching ``section`` on freee, captured "
        "when the ID is set via the picker wizard. Display-only — "
        "the ID is what gets sent to the API.",
    )

    def action_open_freee_section_wizard(self):
        """Open the wizard to pick the matching freee section."""
        self.ensure_one()
        wizard = self.env["freee.section.fetch.wizard"].create(
            {"analytic_account_id": self.id}
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Map freee Section"),
            "res_model": "freee.section.fetch.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_clear_freee_section(self):
        """Unmap the freee section. Exported deal lines whose
        analytic distribution resolves to this account then omit
        ``details[].section_id`` (it is optional — see
        ``freee.export.mapper._map_section``)."""
        self.write(
            {
                "freee_section_id": False,
                "freee_section_name": False,
            }
        )
