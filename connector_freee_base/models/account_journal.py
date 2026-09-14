# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    freee_account_item_id = fields.Integer(
        string="freee Account Item ID",
        copy=False,
        help="Optional freee ``account_item`` id used as a fallback "
        "for invoice lines whose own account has no "
        "``freee_account_item_id`` mapped. The per-account mapping on "
        "``account.account`` always wins when set; this journal-level "
        "value resolves only the lines where the account is left "
        "intentionally unmapped — for example to keep one common "
        "Odoo sales account and split it into different freee "
        "account items per journal (manual customer invoices vs. "
        "EC-site sales). Leave empty when all relevant accounts already "
        "carry "
        "their own freee mapping.",
    )
    freee_account_item_name = fields.Char(
        string="freee Account Item Name",
        copy=False,
        help="Name of the matching freee ``account_item``, captured "
        "when the ID is set via the picker wizard. Display-only — the "
        "ID is what gets sent to the API.",
    )

    # --- Settlement walletable (account) ------------------------------- #
    # When set, invoices on this journal are exported to freee as
    # *settled* deals paid through this walletable (a ``payments[]`` entry).
    # Left empty → the deal is exported *unsettled* (the default).
    freee_walletable_id = fields.Integer(
        string="freee Walletable ID",
        copy=False,
        help="Optional freee ``walletable`` (account) id. When set, every "
        "invoice on this journal is exported as a settled freee deal "
        "paid through this walletable. Leave empty to export the deal as "
        "unsettled — the default behaviour.",
    )
    freee_walletable_type = fields.Char(
        string="freee Walletable Type",
        copy=False,
        help="freee walletable ``type`` (bank_account / credit_card / "
        "wallet), required alongside the id for the deal's "
        "``payments[].from_walletable_type``. Set by the picker wizard.",
    )
    freee_walletable_name = fields.Char(
        string="freee Walletable Name",
        copy=False,
        help="Name of the matching freee walletable, captured when the id "
        "is set via the picker wizard. Display-only.",
    )

    def action_open_freee_account_item_wizard(self):
        """Open the wizard to pick the freee account item for this
        journal (same wizard the chart of accounts uses)."""
        self.ensure_one()
        wizard = self.env["freee.account.item.fetch.wizard"].create(
            {"journal_id": self.id}
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Map freee Account Item"),
            "res_model": "freee.account.item.fetch.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_open_freee_walletable_wizard(self):
        """Open the wizard to pick the freee walletable (account) that
        settles this journal's invoices."""
        self.ensure_one()
        wizard = self.env["freee.walletable.fetch.wizard"].create(
            {"journal_id": self.id}
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Map freee Walletable"),
            "res_model": "freee.walletable.fetch.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_clear_freee_account_item(self):
        """Unmap the per-journal freee account-item fallback → invoice lines
        on this journal whose account is also unmapped will fail to
        export (account-level mapping is the primary, this journal
        value only catches accounts left intentionally unmapped)."""
        self.write(
            {
                "freee_account_item_id": False,
                "freee_account_item_name": False,
            }
        )

    def action_clear_freee_walletable(self):
        """Unmap the walletable → invoices on this journal go back to being
        exported as unsettled deals."""
        self.write(
            {
                "freee_walletable_id": False,
                "freee_walletable_type": False,
                "freee_walletable_name": False,
            }
        )
