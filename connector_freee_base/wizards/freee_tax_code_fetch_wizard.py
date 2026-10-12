# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


from odoo import _, fields, models
from odoo.exceptions import UserError


class FreeeTaxCodeFetchWizard(models.TransientModel):
    _name = "freee.tax.code.fetch.wizard"
    _description = "Fetch freee Tax Codes"

    tax_id = fields.Many2one(
        "account.tax",
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
        "freee.tax.code.fetch.wizard.line",
        "wizard_id",
        string="Available Tax Codes",
    )

    def _default_backend(self):
        return self.env["freee.backend"].search([("state", "=", "authorized")], limit=1)

    def action_fetch(self):
        """Refresh ``line_ids`` from ``GET /api/1/taxes/companies/{company_id}``."""
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
                f"/api/1/taxes/companies/{self.backend_id.external_company_id}",
                "taxes",
            )
        # ``/api/1/taxes/companies/{id}`` is a fixed reference list of
        # ~20–30 freee tax codes and does not page (the get-vs-paginate
        # decision lives in PAGINATED_LIST_KEYS); the atomic replace
        # follows.
        with self.env.cr.savepoint():
            self.line_ids.unlink()
            self.write(
                {
                    "line_ids": [
                        (
                            0,
                            0,
                            {
                                "code": item.get("code"),
                                "name": item.get("name_ja") or item.get("name") or "",
                                "display_category": item.get("display_category")
                                or False,
                                "available": bool(item.get("available", True)),
                            },
                        )
                        for item in items
                        if isinstance(item.get("code"), int)
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


class FreeeTaxCodeFetchWizardLine(models.TransientModel):
    _name = "freee.tax.code.fetch.wizard.line"
    _description = "freee Tax Code Choice"
    _order = "code"

    wizard_id = fields.Many2one(
        "freee.tax.code.fetch.wizard",
        required=True,
        ondelete="cascade",
    )
    code = fields.Integer(string="freee Tax Code", required=True)
    name = fields.Char(required=True)
    display_category = fields.Char()
    available = fields.Boolean(default=True)

    def action_select(self):
        self.ensure_one()
        tax = self.wizard_id.tax_id
        if not tax:
            raise UserError(_("Wizard is not bound to a tax."))
        # No sudo(): the user must have write access on account.tax
        # (typically account.group_account_manager). See the
        # dual-permission note in the account-item wizard.
        tax.write(
            {
                "freee_tax_code": self.code,
                "freee_tax_name": self.name,
            }
        )
        return {"type": "ir.actions.act_window_close"}
