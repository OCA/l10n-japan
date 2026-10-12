# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    freee_item_id = fields.Integer(
        string="freee Item ID",
        help="ID of the matching ``item`` on freee. Stored here "
        "so exporters can populate ``details[].item_id`` in the deal "
        "payload without round-tripping the API on every push.",
    )
    freee_item_name = fields.Char(
        string="freee Item Name",
        help="Name of the matching ``item`` on freee, captured when "
        "the ID is set via the picker wizard. Display-only — the ID "
        "is what gets sent to the API.",
    )

    def action_open_freee_item_wizard(self):
        """Open the wizard to pick the matching freee item."""
        self.ensure_one()
        wizard = self.env["freee.item.fetch.wizard"].create(
            {"product_tmpl_id": self.id}
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Map freee Item"),
            "res_model": "freee.item.fetch.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_clear_freee_item(self):
        """Unmap the freee item. Exported deal lines for this
        product then omit ``details[].item_id`` (it is optional —
        see ``freee.export.mapper._map_item``)."""
        self.write(
            {
                "freee_item_id": False,
                "freee_item_name": False,
            }
        )
