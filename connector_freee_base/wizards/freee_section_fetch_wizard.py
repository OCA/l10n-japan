# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


from odoo import _, fields, models
from odoo.exceptions import UserError


class FreeeSectionFetchWizard(models.TransientModel):
    _name = "freee.section.fetch.wizard"
    _description = "Fetch freee Sections"

    analytic_account_id = fields.Many2one(
        "account.analytic.account",
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
        "freee.section.fetch.wizard.line",
        "wizard_id",
        string="Available Sections",
    )

    def _default_backend(self):
        return self.env["freee.backend"].search([("state", "=", "authorized")], limit=1)

    def action_fetch(self):
        """Refresh ``line_ids`` from ``GET /api/1/sections``."""
        self.ensure_one()
        if not self.backend_id:
            raise UserError(_("Select an authorized freee backend."))
        if not self.backend_id.external_company_id:
            raise UserError(
                _("Backend %s has no freee Company ID set.") % self.backend_id.name
            )
        with self.backend_id.work_on("freee.backend") as work:
            adapter = work.component(usage="backend.adapter")
            sections = adapter.fetch_list(
                "/api/1/sections",
                "sections",
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
                                "long_name": item.get("long_name") or False,
                                "shortcut1": item.get("shortcut1") or False,
                                "shortcut2": item.get("shortcut2") or False,
                                "parent_external_id": item.get("parent_id") or 0,
                            },
                        )
                        for item in sections
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


class FreeeSectionFetchWizardLine(models.TransientModel):
    _name = "freee.section.fetch.wizard.line"
    _description = "freee Section Choice"
    _order = "name"

    wizard_id = fields.Many2one(
        "freee.section.fetch.wizard",
        required=True,
        ondelete="cascade",
    )
    external_id = fields.Integer(string="freee Section ID", required=True)
    name = fields.Char(required=True)
    long_name = fields.Char()
    shortcut1 = fields.Char()
    shortcut2 = fields.Char()
    parent_external_id = fields.Integer(string="Parent freee Section ID")

    def action_select(self):
        self.ensure_one()
        analytic = self.wizard_id.analytic_account_id
        if not analytic:
            raise UserError(_("Wizard is not bound to an analytic account."))
        # No sudo(): the user must have write access on
        # account.analytic.account (typically
        # analytic.group_analytic_accounting). See the dual-permission
        # note in the account-item wizard.
        analytic.write(
            {
                "freee_section_id": self.external_id,
                "freee_section_name": self.name,
            }
        )
        return {"type": "ir.actions.act_window_close"}
