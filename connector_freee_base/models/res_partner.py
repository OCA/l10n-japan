# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    freee_partner_id = fields.Integer(
        string="freee Partner ID",
        help="ID of the matching ``partner`` on freee. Stored here so "
        "exporters can populate ``partner_id`` in the deal payload "
        "without round-tripping the API on every push.",
    )
    freee_partner_code = fields.Char(
        string="freee Partner Code",
        help="External code of the matching ``partner`` on freee. "
        "Stored as a fallback for the ``partner_code`` field of the "
        "deal payload when no ``freee_partner_id`` is available.",
    )
    freee_partner_name = fields.Char(
        string="freee Partner Name",
        help="Name of the matching ``partner`` on freee, captured "
        "when the ID is set via the picker wizard. Display-only — the "
        "ID is what gets sent to the API.",
    )

    def action_open_freee_partner_wizard(self):
        """Open the wizard to pick the matching freee partner."""
        self.ensure_one()
        wizard = self.env["freee.partner.fetch.wizard"].create({"partner_id": self.id})
        return {
            "type": "ir.actions.act_window",
            "name": _("Map freee Partner"),
            "res_model": "freee.partner.fetch.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_clear_freee_partner(self):
        """Unmap the freee partner. Invoices on this partner then fail to
        export (the mapper raises a MappingError so we do not silently
        create freee deals with no partner)."""
        self.write(
            {
                "freee_partner_id": False,
                "freee_partner_code": False,
                "freee_partner_name": False,
            }
        )
