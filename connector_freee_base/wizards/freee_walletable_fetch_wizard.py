# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


from odoo import _, fields, models
from odoo.exceptions import UserError


class FreeeWalletableFetchWizard(models.TransientModel):
    """Pick the freee walletable (account) that settles a journal's invoices.

    Bound to an ``account.journal``: when a walletable is chosen, invoices on
    that journal are exported to freee as *settled* deals (a
    ``payments[]`` entry); leaving the journal unmapped keeps the deal
    *unsettled* (the default).
    """

    _name = "freee.walletable.fetch.wizard"
    _description = "Fetch freee Walletables"

    journal_id = fields.Many2one(
        "account.journal",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    backend_id = fields.Many2one(
        "freee.backend",
        required=True,
        domain="[('state', '=', 'authorized')]",
        default=lambda self: self._default_backend(),
    )
    line_ids = fields.One2many(
        "freee.walletable.fetch.wizard.line",
        "wizard_id",
        string="Available Walletables",
    )

    def _default_backend(self):
        return self.env["freee.backend"].search([("state", "=", "authorized")], limit=1)

    def action_fetch(self):
        """Refresh ``line_ids`` from ``GET /api/1/walletables``."""
        self.ensure_one()
        if not self.backend_id:
            raise UserError(_("Select an authorized freee backend."))
        if not self.backend_id.external_company_id:
            raise UserError(
                _("Backend %s has no freee Company ID set.") % self.backend_id.name
            )
        with self.backend_id.work_on("freee.backend") as work:
            adapter = work.component(usage="backend.adapter")
            walletables = adapter.fetch_list(
                "/api/1/walletables",
                "walletables",
                params={"company_id": self.backend_id.external_company_id},
            )
        # atomic line_ids replace.
        with self.env.cr.savepoint():
            self.line_ids.unlink()
            self.write(
                {
                    "line_ids": [
                        (
                            0,
                            0,
                            {
                                "external_id": w.get("id"),
                                "name": w.get("name") or "",
                                "walletable_type": w.get("type") or False,
                                "bank_id": w.get("bank_id") or 0,
                            },
                        )
                        for w in walletables
                        if w.get("id") is not None
                    ],
                }
            )
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }


class FreeeWalletableFetchWizardLine(models.TransientModel):
    _name = "freee.walletable.fetch.wizard.line"
    _description = "freee Walletable Choice"
    _order = "name"

    wizard_id = fields.Many2one(
        "freee.walletable.fetch.wizard",
        required=True,
        ondelete="cascade",
    )
    external_id = fields.Integer(string="freee Walletable ID", required=True)
    name = fields.Char(required=True)
    walletable_type = fields.Char(string="Type")
    bank_id = fields.Integer(string="Bank ID")

    def action_select(self):
        self.ensure_one()
        journal = self.wizard_id.journal_id
        if not journal:
            raise UserError(_("Wizard is not bound to a journal."))
        # No sudo(): the user must have write access on account.journal
        # (typically account.group_account_manager) on top of the
        # group_freee_admin gate that opened this wizard — the same
        # dual-permission model the account-item wizard uses.
        journal.write(
            {
                "freee_walletable_id": self.external_id,
                "freee_walletable_type": self.walletable_type or False,
                "freee_walletable_name": self.name,
            }
        )
        return {"type": "ir.actions.act_window_close"}
