# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, fields, models
from odoo.exceptions import UserError


class FreeeCompanyFetchWizard(models.TransientModel):
    _name = "freee.company.fetch.wizard"
    _description = "Fetch freee Companies"

    backend_id = fields.Many2one(
        "freee.backend",
        required=True,
        ondelete="cascade",
        readonly=True,
    )
    line_ids = fields.One2many(
        "freee.company.fetch.wizard.line",
        "wizard_id",
        string="Available Companies",
    )


class FreeeCompanyFetchWizardLine(models.TransientModel):
    _name = "freee.company.fetch.wizard.line"
    _description = "freee Company Choice"
    _order = "name"

    wizard_id = fields.Many2one(
        "freee.company.fetch.wizard",
        required=True,
        ondelete="cascade",
    )
    external_id = fields.Char(string="freee Company ID", required=True)
    name = fields.Char(required=True)
    name_kana = fields.Char(string="Name (Kana)")
    display_name = fields.Char()
    role = fields.Char()

    def action_select(self):
        self.ensure_one()
        backend = self.wizard_id.backend_id
        if not backend:
            raise UserError(_("Wizard is not bound to a freee backend."))
        backend.sudo().write(
            {
                "external_company_id": int(self.external_id),
                "external_company_name": self.display_name or self.name,
            }
        )
        return {"type": "ir.actions.act_window_close"}
