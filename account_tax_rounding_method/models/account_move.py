# Copyright 2025 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from collections import defaultdict
from contextlib import contextmanager

from odoo import api, models


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.model_create_multi
    def create(self, vals_list):
        # Group vals by partner_id
        grouped_vals = defaultdict(list)
        for vals in vals_list:
            partner_id = vals.get("partner_id")
            grouped_vals[partner_id].append(vals)
        created_recs = self.browse()
        for partner_id, partner_vals in grouped_vals.items():
            context = self.env.context
            partner = self.env["res.partner"].browse(partner_id or False)
            tax_rounding_method = self.env["account.tax"]._get_tax_rounding_method(
                partner
            )
            context = dict(context, tax_rounding_method=tax_rounding_method)
            self = self.with_context(**context)
            created_recs |= super().create(partner_vals)
        return created_recs

    @contextmanager
    def _sync_dynamic_line(
        self,
        existing_key_fname,
        needed_vals_fname,
        needed_dirty_fname,
        line_type,
        container,
    ):
        if line_type == "tax":
            tax_rounding_method = self.env.context.get("tax_rounding_method")
            moves = container.get("records") or self.env["account.move"]
            partners = self.env["res.partner"]
            if moves:
                partners = moves.mapped("partner_id")
            if not tax_rounding_method:
                tax_rounding_method = self.env["account.tax"]._get_tax_rounding_method(
                    partners
                )
            self = self.with_context(tax_rounding_method=tax_rounding_method)
        with super()._sync_dynamic_line(
            existing_key_fname,
            needed_vals_fname,
            needed_dirty_fname,
            line_type,
            container,
        ) as ret:
            yield ret
