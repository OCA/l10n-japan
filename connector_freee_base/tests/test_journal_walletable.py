# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from .common import FreeeBackendTestCommon


class TestJournalWalletableMapping(FreeeBackendTestCommon):
    """Mapping a freee walletable (account) onto a journal is what flips
    that journal's invoices from unsettled to settled on export."""

    def _sales_journal(self):
        return self.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", self.env.company.id)],
            limit=1,
        )

    def test_wizard_writes_walletable_onto_journal(self):
        journal = self._sales_journal()
        wizard = self.env["freee.walletable.fetch.wizard"].create(
            {"journal_id": journal.id, "backend_id": self.backend.id}
        )
        line = self.env["freee.walletable.fetch.wizard.line"].create(
            {
                "wizard_id": wizard.id,
                "external_id": 4430264,
                "name": "三菱ＵＦＪ（法人）（API）",
                "walletable_type": "bank_account",
                "bank_id": 3843,
            }
        )

        action = line.action_select()

        self.assertEqual(journal.freee_walletable_id, 4430264)
        self.assertEqual(journal.freee_walletable_type, "bank_account")
        self.assertEqual(journal.freee_walletable_name, "三菱ＵＦＪ（法人）（API）")
        self.assertEqual(action["type"], "ir.actions.act_window_close")

    def test_clear_walletable_reverts_to_unsettled(self):
        journal = self._sales_journal()
        journal.write(
            {
                "freee_walletable_id": 4430264,
                "freee_walletable_type": "bank_account",
                "freee_walletable_name": "三菱ＵＦＪ（法人）（API）",
            }
        )
        journal.action_clear_freee_walletable()
        self.assertFalse(journal.freee_walletable_id)
        self.assertFalse(journal.freee_walletable_type)
        self.assertFalse(journal.freee_walletable_name)

    def test_opener_binds_journal(self):
        self.backend.sudo().write({"state": "authorized"})
        journal = self._sales_journal()
        action = journal.action_open_freee_walletable_wizard()
        wizard = self.env["freee.walletable.fetch.wizard"].browse(action["res_id"])
        self.assertEqual(wizard.journal_id, journal)
