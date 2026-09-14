# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


from odoo import _, fields, models
from odoo.exceptions import UserError


class FreeeItemFetchWizard(models.TransientModel):
    _name = "freee.item.fetch.wizard"
    _description = "Fetch freee Items"

    product_tmpl_id = fields.Many2one(
        "product.template",
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
        "freee.item.fetch.wizard.line",
        "wizard_id",
        string="Available Items",
    )

    def _default_backend(self):
        return self.env["freee.backend"].search([("state", "=", "authorized")], limit=1)

    def action_fetch(self):
        """Refresh ``line_ids`` from every page of ``/api/1/items``."""
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
                "/api/1/items",
                "items",
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
                                "shortcut1": item.get("shortcut1") or False,
                                "shortcut2": item.get("shortcut2") or False,
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


class FreeeItemFetchWizardLine(models.TransientModel):
    _name = "freee.item.fetch.wizard.line"
    _description = "freee Item Choice"
    _order = "name"

    wizard_id = fields.Many2one(
        "freee.item.fetch.wizard",
        required=True,
        ondelete="cascade",
    )
    external_id = fields.Integer(string="freee Item ID", required=True)
    name = fields.Char(required=True)
    shortcut1 = fields.Char()
    shortcut2 = fields.Char()
    available = fields.Boolean(default=True)

    def action_select(self):
        self.ensure_one()
        product_tmpl = self.wizard_id.product_tmpl_id
        if not product_tmpl:
            raise UserError(_("Wizard is not bound to a product."))
        # No sudo(): the user must have write access on
        # product.template (granted by Sales / Purchase / Inventory).
        # See the dual-permission note in the account-item wizard.
        product_tmpl.write(
            {
                "freee_item_id": self.external_id,
                "freee_item_name": self.name,
            }
        )
        return {"type": "ir.actions.act_window_close"}
