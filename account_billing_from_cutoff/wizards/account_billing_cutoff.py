# Copyright 2025 Quartile (https://www.quartile.co)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from collections import defaultdict

from odoo import fields, models


class AccountBillingCutoff(models.TransientModel):
    _name = "wiz.account.billing.cutoff"
    _description = "Account Billing From Cutoff"

    cutoff_date = fields.Date(required=True, default=fields.Date.context_today)
    bill_type = fields.Selection(
        selection=[("out_invoice", "Customer Invoice"), ("in_invoice", "Vendor Bill")],
        required=True,
        readonly=True,
    )

    def _allowed_move_types(self):
        if self.bill_type == "out_invoice":
            return ["out_invoice", "out_refund", "out_receipt"]
        return ["in_invoice", "in_refund", "in_receipt"]

    def _get_move_groups(self, moves):
        """Group the moves by the billing they should end up in.

        A move without a recipient bank carries no remittance instruction, so it
        can be billed with any remit-to bank (see
        l10n_jp_summary_invoice.AccountBilling._get_moves). Such moves are added
        to the group of the same partner and currency that does have a bank, so
        that they do not end up in a billing of their own. When several banks
        are in play, the first one is used, res.partner.bank being ordered by
        sequence: that is the bank the moves would have been given by default.
        """
        groups = defaultdict(lambda: self.env["account.move"])
        for move in moves:
            key = (move.partner_id.id, move.currency_id.id, move.partner_bank_id.id)
            groups[key] |= move
        for key in list(groups):
            partner_id, currency_id, bank_id = key
            if bank_id:
                continue
            targets = [
                k for k in groups if k[2] and k[0] == partner_id and k[1] == currency_id
            ]
            if not targets:
                continue
            first_bank = (
                self.env["res.partner.bank"]
                .browse([k[2] for k in targets])
                .sorted()[:1]
            )
            target = next(k for k in targets if k[2] == first_bank.id)
            groups[target] |= groups.pop(key)
        return self._sort_move_groups(groups)

    def _sort_move_groups(self, groups):
        """Order the groups by recipient bank.

        Where a partner has invoices for several recipient banks and a draft
        billing that states none, the first bank is the one that gets to use
        that billing, res.partner.bank being ordered by sequence. Sorting the
        groups here rather than relying on the order the moves happen to come
        in keeps the outcome predictable.
        """
        banks = self.env["res.partner.bank"].browse(
            sorted({key[2] for key in groups if key[2]})
        )
        order = {bank.id: index for index, bank in enumerate(banks.sorted())}
        return dict(sorted(groups.items(), key=lambda item: order.get(item[0][2], -1)))

    def _get_existing_billing_domain(self, partner_id, currency_id, bank_id, bill_type):
        domain = [
            ("partner_id", "=", partner_id),
            ("currency_id", "=", currency_id),
            ("company_id", "=", self.env.company.id),
            ("bill_type", "=", bill_type),
            # The cutoff date is derived from the invoice date, so a billing
            # based on due dates cannot be extended with the moves selected
            # here without making its threshold date inconsistent.
            ("threshold_date_type", "=", "invoice_date"),
            ("state", "=", "draft"),
        ]
        if bank_id:
            # A billing without a remit-to bank does not state where the
            # invoices are to be remitted either, so it can host these moves as
            # well (see l10n_jp_summary_invoice.AccountBilling._get_moves).
            domain += [
                "|",
                ("remit_to_bank_id", "=", bank_id),
                ("remit_to_bank_id", "=", False),
            ]
        return domain

    def _get_existing_billing(self, partner_id, currency_id, bank_id, bill_type):
        """Return the draft billing the moves are to be added to, if any."""
        domain = self._get_existing_billing_domain(
            partner_id, currency_id, bank_id, bill_type
        )
        billings = self.env["account.billing"].search(domain)
        if bank_id:
            bank = self.env["res.partner.bank"].browse(bank_id)
            # A billing that states no remit-to bank can still be committed to
            # one by its lines, and then cannot take moves of another bank (see
            # l10n_jp_summary_invoice.AccountBilling
            # ._check_remit_to_bank_consistency).
            billings = billings.filtered(
                lambda x: not (x.billing_line_ids.move_id.partner_bank_id - bank)
            )
            # Prefer the billing that already states the bank of the moves over
            # one that states none, so that a remittance instruction that is
            # there is not the one left unused.
            return billings.sorted(lambda x: (not x.remit_to_bank_id, x.id))[:1]
        # Any of the billings can host moves without a recipient bank: take the
        # one that has no remit-to bank either, and the one with the first bank
        # otherwise. Ordering them here rather than relying on the order the
        # groups happen to be processed in keeps the outcome predictable.
        return billings.sorted(
            lambda x: (
                bool(x.remit_to_bank_id),
                x.remit_to_bank_id.sequence,
                x.remit_to_bank_id.id,
            )
        )[:1]

    def _search_moves_domain(self):
        billed_move_ids = (
            self.env["account.billing.line"]
            .search(
                [
                    ("billing_id.state", "in", ["draft", "billed"]),
                ]
            )
            .mapped("move_id")
            .ids
        )
        return [
            ("id", "not in", billed_move_ids),
            ("is_not_for_billing", "=", False),
            ("company_id", "=", self.env.company.id),
            ("state", "=", "posted"),
            ("payment_state", "not in", ["paid", "reversed", "invoicing_legacy"]),
            ("move_type", "in", self._allowed_move_types()),
            ("cutoff_date", "<=", self.cutoff_date),
        ]

    def action_create_billings(self):
        moves = self.env["account.move"].search(self._search_moves_domain())
        if not moves:
            return {"type": "ir.actions.act_window_close"}
        billings = self.env["account.billing"]
        for (partner_id, currency_id, bank_id), recs in self._get_move_groups(
            moves
        ).items():
            partner = self.env["res.partner"].browse(partner_id)
            existing_billing = self._get_existing_billing(
                partner_id, currency_id, bank_id, recs._get_billing_type()
            )
            if existing_billing:
                if bank_id and not existing_billing.remit_to_bank_id:
                    # The billing did not state where the invoices are to be
                    # remitted, so take the bank of the moves added to it.
                    existing_billing.remit_to_bank_id = bank_id
                existing_billing.threshold_date = max(
                    existing_billing.threshold_date, self.cutoff_date
                )
                billing_line_dict = existing_billing._get_billing_line_dict(recs)
                existing_billing.billing_line_ids.create(billing_line_dict)
                existing_billing._sort_billing_lines()
                billings |= existing_billing
            else:
                billings |= recs.with_context(
                    default_threshold_date=self.cutoff_date,
                    default_threshold_date_type="invoice_date",
                    # Set the remit-to bank explicitly, as deriving it from the
                    # first billing line would depend on the order of the moves.
                    default_remit_to_bank_id=bank_id,
                )._create_billing(partner)
        xml_id = (
            "account_billing.action_customer_billing"
            if self.bill_type == "out_invoice"
            else "account_billing.action_supplier_billing"
        )
        action = self.env["ir.actions.act_window"]._for_xml_id(xml_id)
        action["domain"] = [("id", "in", billings.ids)]
        return action
