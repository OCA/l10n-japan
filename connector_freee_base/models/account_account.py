# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, fields, models


class AccountAccount(models.Model):
    _inherit = "account.account"

    freee_account_item_id = fields.Integer(
        string="freee Account Item ID",
        help="ID of the matching ``account_item`` on freee. Resolved on "
        "the freee developer console / API and stored here so the mapper "
        "can populate ``details[].account_item_id`` when exporting "
        "invoices.",
    )
    freee_account_item_name = fields.Char(
        string="freee Account Item Name",
        help="Name of the matching ``account_item`` on freee, captured "
        "when the ID is set via the picker wizard. Display-only — the "
        "ID is what gets sent to the API.",
    )

    def action_open_freee_account_item_wizard(self):
        """Open the wizard to pick the matching freee account item."""
        self.ensure_one()
        wizard = self.env["freee.account.item.fetch.wizard"].create(
            {"account_id": self.id}
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Map freee Account Item"),
            "res_model": "freee.account.item.fetch.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_clear_freee_account_item(self):
        """Unmap the freee account item from this account.

        Invoices whose line uses this account then fall back to the
        journal-level fallback ``account.journal.freee_account_item_id``
        if set, otherwise fail to export
        (see ``freee.export.mapper._map_account_item``).
        """
        self.write(
            {
                "freee_account_item_id": False,
                "freee_account_item_name": False,
            }
        )
