# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


from odoo import _, fields, models
from odoo.exceptions import UserError


class FreeeAccountItemFetchWizard(models.TransientModel):
    _name = "freee.account.item.fetch.wizard"
    _description = "Fetch freee Account Items"

    # Exactly one of these is set: the wizard maps a freee account item
    # onto either a chart-of-accounts account or a journal (the latter
    # is the "split sales by journal/walletable" feature).
    account_id = fields.Many2one(
        "account.account",
        readonly=True,
        ondelete="cascade",
    )
    journal_id = fields.Many2one(
        "account.journal",
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
        "freee.account.item.fetch.wizard.line",
        "wizard_id",
        string="Available Account Items",
    )

    def _default_backend(self):
        return self.env["freee.backend"].search([("state", "=", "authorized")], limit=1)

    def action_fetch(self):
        """Refresh ``line_ids`` from ``GET /api/1/account_items``."""
        self.ensure_one()
        if not self.backend_id:
            raise UserError(_("Select an authorized freee backend."))
        if not self.backend_id.external_company_id:
            raise UserError(
                _("Backend %s has no freee Company ID set.") % self.backend_id.name
            )
        with self.backend_id.work_on("freee.backend") as work:
            adapter = work.component(usage="backend.adapter")
            items = adapter.fetch_list(
                "/api/1/account_items",
                "account_items",
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
                                "external_id": item.get("id"),
                                "name": item.get("name") or "",
                                "category": item.get("account_category") or False,
                                "shortcut": item.get("shortcut") or False,
                                "shortcut_num": item.get("shortcut_num") or False,
                                "available": bool(item.get("available", True)),
                            },
                        )
                        for item in items
                        if item.get("id") is not None
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


class FreeeAccountItemFetchWizardLine(models.TransientModel):
    _name = "freee.account.item.fetch.wizard.line"
    _description = "freee Account Item Choice"
    _order = "shortcut_num, name"

    wizard_id = fields.Many2one(
        "freee.account.item.fetch.wizard",
        required=True,
        ondelete="cascade",
    )
    external_id = fields.Integer(string="freee Account Item ID", required=True)
    name = fields.Char(required=True)
    category = fields.Char()
    shortcut = fields.Char()
    shortcut_num = fields.Char(string="Shortcut #")
    available = fields.Boolean(default=True)

    def action_select(self):
        self.ensure_one()
        target = self.wizard_id.journal_id or self.wizard_id.account_id
        if not target:
            raise UserError(_("Wizard is not bound to an account or journal."))
        # No sudo(): the user must have write access on the target model
        # (account.account / account.journal — typically
        # account.group_account_manager) on top of the group_freee_admin
        # gate that opened this wizard. Bypassing that with sudo would
        # silently widen the dual-permission model documented in the
        # README.
        target.write(
            {
                "freee_account_item_id": self.external_id,
                "freee_account_item_name": self.name,
            }
        )
        return {"type": "ir.actions.act_window_close"}
