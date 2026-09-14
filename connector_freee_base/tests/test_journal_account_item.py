# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from .common import FreeeBackendTestCommon


class TestJournalAccountItemMapping(FreeeBackendTestCommon):
    """The account-item picker wizard can map a freee account item onto a
    journal (not only a chart-of-accounts account) — the building block
    of the "split sales by journal/walletable" feature."""

    def _sales_journal(self):
        return self.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", self.env.company.id)],
            limit=1,
        )

    def test_wizard_writes_freee_item_onto_journal(self):
        journal = self._sales_journal()
        self.assertTrue(journal, "a sales journal is expected post_install")
        wizard = self.env["freee.account.item.fetch.wizard"].create(
            {"journal_id": journal.id, "backend_id": self.backend.id}
        )
        line = self.env["freee.account.item.fetch.wizard.line"].create(
            {"wizard_id": wizard.id, "external_id": 7777, "name": "EC Sales"}
        )

        action = line.action_select()

        self.assertEqual(journal.freee_account_item_id, 7777)
        self.assertEqual(journal.freee_account_item_name, "EC Sales")
        self.assertEqual(action["type"], "ir.actions.act_window_close")

    def test_wizard_opener_on_journal_binds_journal_only(self):
        # The wizard's backend_id is required with a default that picks
        # the first *authorized* backend, so authorize the fixture one.
        self.backend.sudo().write({"state": "authorized"})
        journal = self._sales_journal()
        action = journal.action_open_freee_account_item_wizard()
        wizard = self.env["freee.account.item.fetch.wizard"].browse(action["res_id"])
        self.assertEqual(wizard.journal_id, journal)
        self.assertFalse(wizard.account_id)
