# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""freee export mapper abstract base.

Every concrete freee export mapper inherits ``freee.export.mapper``,
mirroring the OCA connector pattern (``prestashop.export.mapper``,
``magento.export.mapper`` …). It bundles:

* the freee collection (`_collection = "freee.backend"`) and the
  ``export.mapper`` usage so concrete mappers only need ``_apply_on``;
* master-data resolution methods that translate an Odoo master record
  (account, tax, analytic account, product, partner) into the freee
  identifier stored on it by the picker wizards in this module —
  reading ``freee_account_item_id``, ``freee_tax_code``,
  ``freee_section_id``, ``freee_item_id``, ``freee_partner_id`` /
  ``freee_partner_code``.

Concrete mappers single-inherit it, e.g.::

    class FreeeAccountMoveExportMapper(Component):
        _name = "freee.account.move.export.mapper"
        _inherit = "freee.export.mapper"
        _apply_on = "freee.account.move"
"""

from odoo import _

from odoo.addons.component.core import AbstractComponent
from odoo.addons.connector.exception import MappingError


class FreeeExportMapper(AbstractComponent):
    _name = "freee.export.mapper"
    _inherit = ["base.export.mapper", "base.freee.connector"]
    _usage = "export.mapper"

    def _map_account_item(self, line):
        # Precedence: account-level mapping is the natural baseline
        # (Odoo account <-> freee account one-to-one) and wins. The
        # journal-level value acts as a fallback for accounts left
        # unmapped — useful for the "split sales by journal/walletable"
        # pattern, where you keep a common Odoo sales account unmapped at
        # the chart-of-accounts level and resolve the freee account_item
        # per journal (manual sales vs. EC-site sales) instead.
        # getattr-guarded so the base stays usable from feature modules
        # whose "line" is not an account.move.line.
        account = line.account_id
        if account.freee_account_item_id:
            return account.freee_account_item_id
        move = getattr(line, "move_id", False)
        journal = getattr(move, "journal_id", False) if move else False
        journal_item = getattr(journal, "freee_account_item_id", False) or False
        if journal_item:
            return journal_item
        # Reuse the getattr-guarded ``move`` / ``journal`` from above:
        # a feature-module "line" without a move must still fail with a
        # clean MappingError, not an AttributeError while building the
        # message.
        raise MappingError(
            _(
                "Account %(account)s has no freee_account_item_id set "
                "and journal %(journal)s has no freee fallback; map one "
                "of them before exporting %(invoice)s."
            )
            % {
                "account": account.display_name,
                "journal": journal.display_name if journal else _("(none)"),
                "invoice": move.display_name if move else line.display_name,
            }
        )

    def _pick_freee_tax(self, line):
        """Return the ``account.tax`` carrying ``freee_tax_code`` for this
        line.

        The freee Deals API treats ``details[].tax_code`` as a single
        scalar — a freee deal row cannot carry more than one tax code.
        We therefore refuse to export rows where multiple taxes have a
        ``freee_tax_code`` mapped: silently picking "the first one"
        would drop the others (e.g. stamp duty stacked on top of
        consumption tax) without any audit trail.
        """
        taxes_with_code = line.tax_ids.filtered(lambda t: t.freee_tax_code)
        if not taxes_with_code:
            raise MappingError(
                _(
                    "Invoice line '%(line)s' on %(invoice)s has no tax with "
                    "freee_tax_code set; map every applicable tax via the "
                    "freee wizard before exporting."
                )
                % {
                    "line": line.name,
                    "invoice": line.move_id.display_name,
                }
            )
        if len(taxes_with_code) > 1:
            raise MappingError(
                _(
                    "Invoice line '%(line)s' on %(invoice)s carries "
                    "multiple taxes with freee_tax_code mapped "
                    "(%(codes)s). freee's details[].tax_code is a single "
                    "scalar so multi-tax rows cannot be expressed on "
                    "freee — split the row, or unmap one of the taxes "
                    "before exporting."
                )
                % {
                    "line": line.name,
                    "invoice": line.move_id.display_name,
                    "codes": ", ".join(str(t.freee_tax_code) for t in taxes_with_code),
                }
            )
        return taxes_with_code

    def _map_item(self, line):
        # Optional product → freee item mapping. The freee item
        # id is stored on product.template via the picker wizard in
        # connector_freee_base. Lines with no product, or whose product
        # has no freee_item_id mapped, omit item_id from the payload —
        # freee rejects a 0/false against the integer-typed item_id
        # (same reason section_id is conditionally included).
        product = line.product_id
        if not product:
            return False
        return product.product_tmpl_id.freee_item_id or False

    def _map_section(self, line):
        # Optional analytic-account → freee section mapping.
        # We pick the first analytic account in the line's distribution
        # and forward its ``freee_section_id`` (set via the picker
        # wizard in connector_freee_base). Lines without a mapped
        # analytic account simply omit ``section_id`` from the payload.
        distribution = line.analytic_distribution or {}
        analytic_model = self.env["account.analytic.account"]
        for key in distribution:
            first = str(key).split(",")[0]
            if not first.isdigit():
                continue
            analytic = analytic_model.browse(int(first))
            if analytic.exists() and analytic.freee_section_id:
                return analytic.freee_section_id
        return False

    def _map_partner(self, partner):
        """Return the freee deal partner key for ``partner``.

        freee accepts either ``partner_id`` (integer, freee's own id)
        or ``partner_code`` (string, external code). Precision-first:
        an explicitly picked ``freee_partner_id`` is unambiguous so it
        wins; otherwise the ``freee_partner_code`` chosen in the same
        picker wizard is sent as the string ``partner_code``.

        Without either identifier we **refuse to export**. Posting a
        deal with no partner silently pollutes freee's sales-by-partner /
        AR aging reports — far worse than a failed export job the
        operator can clearly fix by mapping the partner.
        """
        if not partner:
            raise MappingError(
                _(
                    "Invoice has no partner; cannot export to freee. "
                    "Set a partner on the invoice or exclude it from "
                    "freee export."
                )
            )
        if partner.freee_partner_id:
            return {"partner_id": partner.freee_partner_id}
        if partner.freee_partner_code:
            return {"partner_code": str(partner.freee_partner_code)}
        raise MappingError(
            _(
                "Partner '%(partner)s' has no freee mapping "
                "(neither freee_partner_id nor freee_partner_code). "
                "Open the partner, run *Pick from freee* and map it "
                "before exporting — unmapped partners would otherwise "
                "land on freee with no partner and silently pollute the "
                "sales-by-partner / AR aging reports."
            )
            % {"partner": partner.display_name}
        )
