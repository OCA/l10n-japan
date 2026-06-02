# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""Parsing asserted against *real* freee Accounting API responses.

The JSON in ``tests/fixtures/`` was captured live from freee against a
development company (read-only GETs), then trimmed. Each test feeds a
fixture through the mocked HTTP layer so a freee-side field rename or
type change (e.g. tax ``code`` switching from int to str) fails here
instead of silently in production.
"""

from contextlib import contextmanager
from datetime import timedelta
from unittest import mock

from odoo import fields

from .common import FreeeBackendTestCommon, load_fixture, make_response

ADAPTER_REQUESTS = "odoo.addons.connector_freee_base.components.adapter.requests"

# freee development company the fixtures were captured from.
FREEE_COMPANY_ID = 12195334


def _route(url):
    """Map a freee API URL to the fixture that endpoint really returns.

    Order matters: the sub-resource paths must be tested before the bare
    ``/api/1/companies`` so ``/companies/{id}`` is not shadowed.
    """
    if "/api/1/taxes/companies/" in url:
        return load_fixture("taxes")
    if "/api/1/account_items" in url:
        return load_fixture("account_items")
    if "/api/1/items" in url:
        return load_fixture("items")
    if "/api/1/sections" in url:
        return load_fixture("sections")
    if "/api/1/walletables" in url:
        return load_fixture("walletables")
    if "/api/1/partners" in url:
        return load_fixture("partners")
    if "/api/1/deals" in url:
        return load_fixture("deal")
    if "/api/1/companies/" in url:
        return load_fixture("company")
    if url.endswith("/api/1/companies"):
        return load_fixture("companies")
    raise AssertionError(f"unexpected freee URL in test: {url}")


class TestFreeeRealPayloads(FreeeBackendTestCommon):
    def setUp(self):
        super().setUp()
        self.backend._write_secret("encrypted_access_token", "AT-test")
        self.backend.sudo().write(
            {
                "state": "authorized",
                "external_company_id": FREEE_COMPANY_ID,
                "token_expires_at": fields.Datetime.now() + timedelta(hours=1),
            }
        )

    @contextmanager
    def _freee(self):
        """Patch the HTTP seam so every freee call returns the real
        captured payload for that endpoint."""
        with mock.patch(f"{ADAPTER_REQUESTS}.request") as req:
            req.side_effect = lambda method, url, **kw: make_response(
                200, json_body=_route(url)
            )
            yield req

    # ----------------------------------------------------------------- #
    # Master-data discovery wizards                                      #
    # ----------------------------------------------------------------- #
    def test_companies_payload(self):
        with self._freee():
            action = self.backend.action_fetch_companies()
        wizard = self.env["freee.company.fetch.wizard"].browse(action["res_id"])
        self.assertEqual(len(wizard.line_ids), 2)
        bound = wizard.line_ids.filtered(
            lambda line: line.external_id == str(FREEE_COMPANY_ID)
        )
        self.assertEqual(bound.display_name, "開発用テスト事業所")
        self.assertEqual(bound.role, "admin")

    def test_company_payload_and_connection_test(self):
        with self._freee():
            result = self.backend.action_test_connection()
        self.assertEqual(result["params"]["type"], "success")

    def test_partners_payload(self):
        partner = self.env["res.partner"].create({"name": "Fixture Co."})
        wizard = self.env["freee.partner.fetch.wizard"].create(
            {"partner_id": partner.id, "backend_id": self.backend.id}
        )
        with self._freee():
            wizard.action_fetch()
        self.assertEqual(len(wizard.line_ids), 3)
        first = wizard.line_ids.filtered(lambda line: line.external_id == 103504311)
        self.assertEqual(first.name, "[demo]株式会社freee企画")
        self.assertTrue(first.available)

    def test_taxes_payload(self):
        tax = self._a_sale_tax()
        wizard = self.env["freee.tax.code.fetch.wizard"].create(
            {"tax_id": tax.id, "backend_id": self.backend.id}
        )
        with self._freee():
            wizard.action_fetch()
        self.assertEqual(len(wizard.line_ids), 5)
        line = wizard.line_ids.filtered(lambda line: line.code == 129)
        # freee returns tax code as an *int*; the model field is Integer.
        self.assertEqual(line.code, 129)
        self.assertEqual(line.name, "課税売上10%")
        self.assertEqual(line.display_category, "tax_10")

    def test_account_items_payload(self):
        account = self.env["account.account"].search(
            [
                ("account_type", "=", "income"),
                ("company_ids", "in", self.env.company.id),
            ],
            limit=1,
        )
        wizard = self.env["freee.account.item.fetch.wizard"].create(
            {"account_id": account.id, "backend_id": self.backend.id}
        )
        with self._freee():
            wizard.action_fetch()
        self.assertEqual(len(wizard.line_ids), 3)
        line = wizard.line_ids.filtered(lambda line: line.external_id == 972197136)
        self.assertEqual(line.name, "その他有価証券評価差額金")
        self.assertEqual(line.category, "他有価証券評価差額金")
        self.assertEqual(line.shortcut, "SONOTAYU")
        self.assertEqual(line.shortcut_num, "570")

    def test_items_payload(self):
        tmpl = self.env["product.template"].create({"name": "Fixture Product"})
        wizard = self.env["freee.item.fetch.wizard"].create(
            {"product_tmpl_id": tmpl.id, "backend_id": self.backend.id}
        )
        with self._freee():
            wizard.action_fetch()
        self.assertEqual(len(wizard.line_ids), 3)
        line = wizard.line_ids.filtered(lambda line: line.external_id == 241425920)
        self.assertEqual(line.name, "イラストデザイン")

    def test_sections_payload(self):
        plan = self.env["account.analytic.plan"].search([], limit=1) or self.env[
            "account.analytic.plan"
        ].create({"name": "Fixture Plan"})
        analytic = self.env["account.analytic.account"].create(
            {"name": "Fixture Analytic", "plan_id": plan.id}
        )
        wizard = self.env["freee.section.fetch.wizard"].create(
            {"analytic_account_id": analytic.id, "backend_id": self.backend.id}
        )
        with self._freee():
            wizard.action_fetch()
        self.assertEqual(len(wizard.line_ids), 5)
        line = wizard.line_ids.filtered(lambda line: line.external_id == 3615078)
        self.assertEqual(line.name, "営業部")
        self.assertEqual(line.parent_external_id, 0)  # null parent_id -> 0

    def test_walletables_payload(self):
        """Walletable list parses from a real captured freee
        response through the picker wizard — pins the real field shape
        (``bank_id`` nullable, ``type`` enum, full-width Japanese
        names) so a freee-side change is caught here."""
        journal = self.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", self.env.company.id)],
            limit=1,
        )
        wizard = self.env["freee.walletable.fetch.wizard"].create(
            {"journal_id": journal.id, "backend_id": self.backend.id}
        )
        with self._freee():
            wizard.action_fetch()

        self.assertEqual(len(wizard.line_ids), 2)
        bank = wizard.line_ids.filtered(lambda x: x.external_id == 4430264)
        self.assertEqual(bank.name, "三菱ＵＦＪ（法人）（API）")
        self.assertEqual(bank.walletable_type, "bank_account")
        self.assertEqual(bank.bank_id, 3843)

        cash = wizard.line_ids.filtered(lambda x: x.external_id == 7168567)
        self.assertEqual(cash.name, "現金")
        self.assertEqual(cash.walletable_type, "wallet")
        # cash (wallet) has no linked bank — freee returns JSON null,
        # the wizard stores it as 0 (Integer field).
        self.assertEqual(cash.bank_id, 0)

    # ----------------------------------------------------------------- #
    # Helpers                                                            #
    # ----------------------------------------------------------------- #
    def _a_sale_tax(self):
        tax = self.env["account.tax"].search(
            [
                ("type_tax_use", "=", "sale"),
                ("company_id", "=", self.env.company.id),
            ],
            limit=1,
        )
        if tax:
            return tax
        group = self.env["account.tax.group"].search(
            [("company_id", "=", self.env.company.id)], limit=1
        ) or self.env["account.tax.group"].create(
            {"name": "Fixture Tax Group", "company_id": self.env.company.id}
        )
        return self.env["account.tax"].create(
            {
                "name": "Fixture 10%",
                "amount": 10.0,
                "type_tax_use": "sale",
                "tax_group_id": group.id,
            }
        )
