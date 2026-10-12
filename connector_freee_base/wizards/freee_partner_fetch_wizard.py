# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


from odoo import _, fields, models
from odoo.exceptions import UserError


class FreeePartnerFetchWizard(models.TransientModel):
    _name = "freee.partner.fetch.wizard"
    _description = "Fetch freee Partners"

    partner_id = fields.Many2one(
        "res.partner",
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
    name_filter = fields.Char(
        string="Filter by Name",
        help="Optional ``keyword`` query parameter forwarded to "
        "``/api/1/partners``. Server-side substring match on the "
        "freee partner name.",
    )
    line_ids = fields.One2many(
        "freee.partner.fetch.wizard.line",
        "wizard_id",
        string="Available Partners",
    )

    def _default_backend(self):
        return self.env["freee.backend"].search([("state", "=", "authorized")], limit=1)

    def action_fetch(self):
        """Refresh ``line_ids`` from every page of ``/api/1/partners``."""
        self.ensure_one()
        if not self.backend_id:
            raise UserError(_("Select an authorized freee backend."))
        if not self.backend_id.external_company_id:
            raise UserError(
                _("Backend %s has no freee Company ID set.") % self.backend_id.name
            )
        params = {"company_id": self.backend_id.external_company_id}
        if self.name_filter:
            params["keyword"] = self.name_filter
        with self.backend_id.work_on("freee.backend") as work:
            adapter = work.component(usage="backend.adapter")
            partners = adapter.fetch_list("/api/1/partners", "partners", params=params)
        # rebuild ``line_ids`` atomically. Under a savepoint so a
        # mid-write failure rolls back to the previous list instead of
        # leaving an empty wizard the operator cannot tell apart from
        # "freee returned nothing".
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
                                "code": item.get("code") or False,
                                "name": item.get("name") or "",
                                "shortcut1": item.get("shortcut1") or False,
                                "shortcut2": item.get("shortcut2") or False,
                                "available": bool(item.get("available", True)),
                            },
                        )
                        for item in partners
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


class FreeePartnerFetchWizardLine(models.TransientModel):
    _name = "freee.partner.fetch.wizard.line"
    _description = "freee Partner Choice"
    _order = "name"

    wizard_id = fields.Many2one(
        "freee.partner.fetch.wizard",
        required=True,
        ondelete="cascade",
    )
    external_id = fields.Integer(string="freee Partner ID", required=True)
    code = fields.Char()
    name = fields.Char(required=True)
    shortcut1 = fields.Char()
    shortcut2 = fields.Char()
    available = fields.Boolean(default=True)

    def action_select(self):
        self.ensure_one()
        partner = self.wizard_id.partner_id
        if not partner:
            raise UserError(_("Wizard is not bound to a partner."))
        # No sudo(): the user must have write access on res.partner.
        # See the dual-permission note in the account-item wizard.
        partner.write(
            {
                "freee_partner_id": self.external_id,
                "freee_partner_code": self.code or False,
                "freee_partner_name": self.name,
            }
        )
        return {"type": "ir.actions.act_window_close"}
