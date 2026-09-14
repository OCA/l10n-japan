# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""Defensive branches the feature-focused suites do not reach: the
job-result formatting helpers, the credential / authorization guards on
``freee.backend``, the admin-alert scheduling, the adapter rate-limit
bookkeeping and the wizard input guards. Pinned here so the error paths
stay covered.
"""

from contextlib import contextmanager
from datetime import timedelta
from unittest import mock

from odoo import fields, tools
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.component.core import Component
from odoo.addons.component.tests.common import TransactionComponentRegistryCase
from odoo.addons.connector.exception import MappingError
from odoo.addons.queue_job.exception import RetryableJobError

from ..components import job_result
from .common import _TEST_ENCRYPTION_KEY, FreeeBackendTestCommon, make_response

ADAPTER_REQUESTS = "odoo.addons.connector_freee_base.components.adapter.requests"
ADAPTER_MOD = "odoo.addons.connector_freee_base.components.adapter"
ADAPTER_LOG = "odoo.addons.connector_freee_base.components.adapter"
BACKEND_LOG = "odoo.addons.connector_freee_base.models.freee_backend"


class TestJobResult(FreeeBackendTestCommon):
    def test_format_keeps_unicode_and_indents(self):
        out = job_result.format_job_result({"会社": "freee", "n": 1})
        # ensure_ascii=False keeps Japanese readable; indent=2 pretty-prints.
        self.assertIn("会社", out)
        self.assertIn("\n", out)

    def test_debug_payload_hidden_by_default(self):
        binding = mock.MagicMock()
        binding.backend_id.sudo.return_value.debug_log_request_payload = False
        self.assertEqual(job_result.debug_payload(binding, {"a": 1}, {"b": 2}), {})

    def test_debug_payload_exposed_when_toggle_on(self):
        binding = mock.MagicMock()
        binding.backend_id.sudo.return_value.debug_log_request_payload = True
        self.assertEqual(
            job_result.debug_payload(binding, {"a": 1}, {"b": 2}),
            {"request": {"a": 1}, "response": {"b": 2}},
        )


class TestBackendGuards(FreeeBackendTestCommon):
    def test_write_secret_empty_clears_ciphertext(self):
        self.backend._write_secret("encrypted_access_token", "AT")
        self.assertTrue(self.backend.sudo().encrypted_access_token)
        # A falsy value stores False rather than an encrypted blob.
        self.backend._write_secret("encrypted_access_token", "")
        self.assertFalse(self.backend.sudo().encrypted_access_token)

    def test_get_access_token_without_token_raises(self):
        # Not expired (so no refresh attempt) but no token stored: the
        # backend is effectively unauthorized.
        self.backend.sudo().write(
            {
                "state": "authorized",
                "token_expires_at": fields.Datetime.now() + timedelta(hours=1),
            }
        )
        with self.assertRaises(UserError):
            self.backend.sudo()._get_access_token()

    @mute_logger(BACKEND_LOG)
    def test_store_token_response_without_access_token_raises(self):
        resp = make_response(200, json_body={"refresh_token": "RT"})
        with self.assertRaises(UserError):
            self.backend.sudo()._store_token_response(resp)

    def test_fetch_companies_requires_authorized(self):
        self.backend.sudo().write({"state": "draft"})
        with self.assertRaises(UserError):
            self.backend.action_fetch_companies()

    def test_fetch_companies_empty_list_raises(self):
        self.backend._write_secret("encrypted_access_token", "AT")
        self.backend.sudo().write(
            {
                "state": "authorized",
                "external_company_id": "1234",
                "token_expires_at": fields.Datetime.now() + timedelta(hours=1),
            }
        )
        with mock.patch(f"{ADAPTER_REQUESTS}.request") as req:
            req.return_value = make_response(200, json_body={"companies": []})
            with self.assertRaises(UserError):
                self.backend.action_fetch_companies()

    def test_test_connection_requires_company_id(self):
        self.backend.sudo().write({"state": "authorized", "external_company_id": False})
        with self.assertRaises(UserError):
            self.backend.action_test_connection()


class TestAdminNotify(FreeeBackendTestCommon):
    def _admin_user(self):
        group = self.env.ref("connector_freee_base.group_freee_admin")
        return self.env["res.users"].create(
            {
                "name": "Freee Admin Cov",
                "login": "freee_admin_cov",
                "email": "fa-cov@test.test",
                "groups_id": [(4, group.id)],
            }
        )

    def test_notify_unknown_activity_xmlid_is_noop(self):
        # activity type ref missing -> early return, no crash.
        self.backend._notify_freee_admins(
            "connector_freee_base.does_not_exist", "S", "N"
        )

    def test_clear_unknown_activity_xmlid_is_noop(self):
        self.backend._clear_freee_admin_activities(
            "connector_freee_base.does_not_exist"
        )

    def test_clear_removes_open_activities(self):
        self._admin_user()
        self.backend._notify_freee_admins("mail.mail_activity_data_todo", "S", "N")
        domain = [
            ("res_model", "=", "freee.backend"),
            ("res_id", "=", self.backend.id),
        ]
        self.assertTrue(self.env["mail.activity"].search_count(domain))
        self.backend._clear_freee_admin_activities("mail.mail_activity_data_todo")
        self.assertFalse(self.env["mail.activity"].search_count(domain))

    def test_notify_schedules_activity_and_dedupes(self):
        self._admin_user()
        self.backend._notify_freee_admins(
            "mail.mail_activity_data_todo", "Summary", "Note"
        )
        domain = [
            ("res_model", "=", "freee.backend"),
            ("res_id", "=", self.backend.id),
        ]
        first = self.env["mail.activity"].search_count(domain)
        self.assertTrue(first)
        # Second call must not pile a duplicate to-do up under a cron.
        self.backend._notify_freee_admins(
            "mail.mail_activity_data_todo", "Summary", "Note"
        )
        self.assertEqual(self.env["mail.activity"].search_count(domain), first)

    def test_notify_without_admin_group_returns(self):
        real_ref = type(self.env).ref

        def fake_ref(env_self, xmlid, raise_if_not_found=True):
            if xmlid == "connector_freee_base.group_freee_admin":
                return env_self["res.groups"]  # empty -> falsy
            return real_ref(env_self, xmlid, raise_if_not_found=raise_if_not_found)

        with mock.patch.object(type(self.env), "ref", fake_ref):
            # Reaches the admin-group guard and returns without scheduling.
            self.backend._notify_freee_admins("mail.mail_activity_data_todo", "S", "N")

    @mute_logger(BACKEND_LOG)
    def test_notify_swallows_message_post_failure(self):
        self._admin_user()
        with mock.patch.object(
            type(self.backend),
            "message_post",
            side_effect=RuntimeError("mail down"),
        ):
            # The chatter push failing must not break the alert path.
            self.backend._notify_freee_admins("mail.mail_activity_data_todo", "S", "N")


class TestAdapterEdges(FreeeBackendTestCommon):
    def setUp(self):
        super().setUp()
        self.backend._write_secret("encrypted_access_token", "AT-test")
        self.backend.sudo().write(
            {
                "state": "authorized",
                "token_expires_at": fields.Datetime.now() + timedelta(hours=1),
            }
        )

    @contextmanager
    def _adapter(self):
        with self.backend.work_on(self.backend._name) as work:
            yield work.component(usage="backend.adapter")

    def test_delete_uses_delete_verb(self):
        with (
            self._adapter() as adapter,
            mock.patch(f"{ADAPTER_REQUESTS}.request") as req,
        ):
            req.return_value = make_response(200, json_body={"ok": True})
            adapter.delete("/api/1/deals/9")
        self.assertEqual(req.call_args.args[0], "DELETE")

    def test_put_uses_put_verb(self):
        with (
            self._adapter() as adapter,
            mock.patch(f"{ADAPTER_REQUESTS}.request") as req,
        ):
            req.return_value = make_response(200, json_body={"ok": True})
            adapter.put("/api/1/deals/9", payload={"x": 1})
        self.assertEqual(req.call_args.args[0], "PUT")

    def test_throttle_disabled_when_interval_non_positive(self):
        from ..components import adapter as amod

        with (
            self._adapter() as adapter,
            mock.patch(f"{ADAPTER_REQUESTS}.request") as req,
            mock.patch.object(amod, "_REQUEST_INTERVAL_SECONDS", 0),
        ):
            req.return_value = make_response(200, json_body={"ok": 1})
            adapter.get("/api/1/users/me")
        req.assert_called_once()

    def test_throttle_skips_when_lock_unavailable(self):
        from ..components.adapter import _RATE_LIMIT_LOCK_NS

        # Hold the per-backend advisory lock on a *separate* connection so
        # the adapter's pg_try_advisory_lock fails and it skips the throttle.
        with self.env.registry.cursor() as lock_cr:
            lock_cr.execute(
                "SELECT pg_advisory_lock(%s, %s)",
                (_RATE_LIMIT_LOCK_NS, self.backend.id),
            )
            try:
                with (
                    self._adapter() as adapter,
                    mock.patch(f"{ADAPTER_REQUESTS}.request") as req,
                ):
                    req.return_value = make_response(200, json_body={"ok": 1})
                    adapter.get("/api/1/users/me")
                req.assert_called_once()
            finally:
                lock_cr.execute(
                    "SELECT pg_advisory_unlock(%s, %s)",
                    (_RATE_LIMIT_LOCK_NS, self.backend.id),
                )

    @mute_logger(ADAPTER_LOG)
    def test_throttle_bookkeeping_failure_is_swallowed(self):
        with (
            self._adapter() as adapter,
            mock.patch(f"{ADAPTER_REQUESTS}.request") as req,
        ):
            req.return_value = make_response(200, json_body={"ok": 1})
            with mock.patch.object(
                type(self.env["ir.config_parameter"]),
                "set_param",
                side_effect=RuntimeError("cfg boom"),
            ):
                # Throttle write fails but the API call still goes through.
                adapter.get("/api/1/users/me")
        req.assert_called_once()

    @mute_logger(ADAPTER_LOG)
    def test_429_non_integer_retry_after_uses_default(self):
        with (
            self._adapter() as adapter,
            mock.patch(f"{ADAPTER_REQUESTS}.request") as req,
        ):
            req.return_value = make_response(
                429, json_body={"x": 1}, headers={"Retry-After": "soon"}
            )
            with self.assertRaises(RetryableJobError):
                adapter.get("/api/1/users/me")


FETCH_WIZARDS = [
    "freee.account.item.fetch.wizard",
    "freee.item.fetch.wizard",
    "freee.partner.fetch.wizard",
    "freee.section.fetch.wizard",
    "freee.tax.code.fetch.wizard",
    "freee.walletable.fetch.wizard",
]

LINE_WIZARDS = [
    "freee.account.item.fetch.wizard",
    "freee.company.fetch.wizard",
    "freee.item.fetch.wizard",
    "freee.partner.fetch.wizard",
    "freee.section.fetch.wizard",
    "freee.tax.code.fetch.wizard",
    "freee.walletable.fetch.wizard",
]


class TestWizardGuards(FreeeBackendTestCommon):
    def setUp(self):
        super().setUp()
        # A draft backend with no freee Company ID, to exercise the
        # "company id missing" branch of every fetch wizard.
        self.no_company = self.env["freee.backend"].create(
            {"name": "No Company", "client_id": "c", "client_secret": "s"}
        )

    def test_fetch_requires_backend_and_company(self):
        for model in FETCH_WIZARDS:
            # In-memory records dodge the wizards' required context fields
            # (backend_id, and the bound record they open from) so we can
            # reach the friendly action_fetch guards directly.
            with self.assertRaises(UserError):
                self.env[model].new({}).action_fetch()  # no backend
            with self.assertRaises(UserError):
                # Backend chosen but it has no freee Company ID.
                self.env[model].new({"backend_id": self.no_company.id}).action_fetch()

    def test_line_select_requires_bound_target(self):
        for model in LINE_WIZARDS:
            # In-memory records: the parent wizard is bound to neither a
            # backend nor a target record, so action_select must refuse.
            wizard = self.env[model].new({})
            line = self.env[model + ".line"].new({})
            line.wizard_id = wizard
            with self.assertRaises(UserError):
                line.action_select()

    def test_partner_fetch_forwards_keyword(self):
        backend = self.env["freee.backend"].create(
            {
                "name": "Authorized",
                "client_id": "c",
                "client_secret": "s",
                "external_company_id": "4242",
            }
        )
        backend._write_secret("encrypted_access_token", "AT")
        backend.sudo().write(
            {
                "state": "authorized",
                "token_expires_at": fields.Datetime.now() + timedelta(hours=1),
            }
        )
        partner = self.env["res.partner"].create({"name": "Keyword Co."})
        wizard = self.env["freee.partner.fetch.wizard"].create(
            {
                "backend_id": backend.id,
                "partner_id": partner.id,
                "name_filter": "acme",
            }
        )
        with mock.patch(f"{ADAPTER_REQUESTS}.request") as req:
            req.return_value = make_response(200, json_body={"partners": []})
            wizard.action_fetch()
        self.assertEqual(req.call_args.kwargs["params"]["keyword"], "acme")


@tagged("post_install", "-at_install")
class TestExportMapperMixin(TransactionComponentRegistryCase):
    """Exercise the shared ``freee.export.mapper`` master-data helpers via a
    test-only concrete mapper.

    ``freee.export.mapper`` is an abstract mixin whose only production
    consumers live in feature modules (e.g. connector_freee_invoice). To
    cover it in the base module alone, we register a throwaway concrete
    mapper on ``account.move`` in an isolated component registry (the OCA
    ``ComponentRegistryCase`` pattern) and call the helpers directly.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The freee.backend create path requires the odoo.conf-only key.
        original_key = tools.config.get("connector_freee_base_encryption_key")
        tools.config["connector_freee_base_encryption_key"] = _TEST_ENCRYPTION_KEY

        def _restore_key():
            if original_key is None:
                tools.config.pop("connector_freee_base_encryption_key", None)
            else:
                tools.config["connector_freee_base_encryption_key"] = original_key

        cls.addClassCleanup(_restore_key)
        company = cls.env.company
        cls.partner = cls.env["res.partner"].create({"name": "Mapper Co."})
        # A mapped income account, plus an unmapped one for the fallback /
        # error paths of _map_account_item.
        cls.income = cls.env["account.account"].search(
            [("account_type", "=", "income"), ("company_ids", "in", company.id)],
            limit=1,
        )
        cls.income.freee_account_item_id = 9001
        cls.income_unmapped = cls.env["account.account"].create(
            {"name": "Unmapped Income", "code": "FRUNM", "account_type": "income"}
        )
        # Two sale journals: one carrying a freee account-item fallback, one
        # without any freee mapping.
        cls.journal_mapped = cls.env["account.journal"].create(
            {
                "name": "JM",
                "type": "sale",
                "code": "FRJM",
                "freee_account_item_id": 7001,
            }
        )
        cls.journal_plain = cls.env["account.journal"].create(
            {"name": "JP", "type": "sale", "code": "FRJP"}
        )
        # Taxes: two freee-mapped (for the single / multi cases) and one with
        # no freee_tax_code.
        tax_group = cls.env["account.tax.group"].search(
            [("company_id", "=", company.id)], limit=1
        ) or cls.env["account.tax.group"].create(
            {"name": "G", "company_id": company.id}
        )
        cls.tax_a = cls.env["account.tax"].create(
            {
                "name": "A10",
                "amount": 10,
                "type_tax_use": "sale",
                "freee_tax_code": 21,
                "tax_group_id": tax_group.id,
            }
        )
        cls.tax_b = cls.env["account.tax"].create(
            {
                "name": "B8",
                "amount": 8,
                "type_tax_use": "sale",
                "freee_tax_code": 2,
                "tax_group_id": tax_group.id,
            }
        )
        cls.tax_nocode = cls.env["account.tax"].create(
            {
                "name": "NoCode",
                "amount": 0,
                "type_tax_use": "sale",
                "tax_group_id": tax_group.id,
            }
        )
        # Products: one mapped to a freee item, one not.
        cls.product_mapped = cls.env["product.product"].create({"name": "PM"})
        cls.product_mapped.product_tmpl_id.freee_item_id = 5001
        cls.product_plain = cls.env["product.product"].create({"name": "PP"})
        # An analytic account mapped to a freee section.
        plan = cls.env["account.analytic.plan"].create({"name": "Plan"})
        cls.analytic = cls.env["account.analytic.account"].create(
            {"name": "AA", "plan_id": plan.id, "freee_section_id": 3001}
        )

    def setUp(self):
        super().setUp()
        self._setup_registry(self)
        self.addCleanup(self._teardown_registry, self)
        # Load this addon's components into the isolated test registry and
        # register a concrete mapper applying the abstract mixin.
        self._load_module_components("connector_freee_base")

        class FreeeCoverageExportMapper(Component):
            _name = "freee.coverage.export.mapper"
            _inherit = "freee.export.mapper"
            _apply_on = "account.move"

        self._build_components(FreeeCoverageExportMapper)
        self.backend = self.env["freee.backend"].create(
            {
                "name": "Mapper Backend",
                "client_id": "cid",
                "client_secret": "cse",
                "external_company_id": "4242",
            }
        )

    def _mapper(self):
        with self.backend.work_on(
            "account.move", components_registry=self.comp_registry
        ) as work:
            return work.component(usage="export.mapper", model_name="account.move")

    def _line(
        self, account=None, journal=None, taxes=None, product=None, analytic=None
    ):
        line_vals = {
            "name": "Line",
            "quantity": 1,
            "price_unit": 1000,
            "account_id": (account or self.income).id,
        }
        if taxes is not None:
            line_vals["tax_ids"] = [(6, 0, [t.id for t in taxes])]
        if product is not None:
            line_vals["product_id"] = product.id
        if analytic is not None:
            line_vals["analytic_distribution"] = analytic
        move_vals = {
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "invoice_line_ids": [(0, 0, line_vals)],
        }
        if journal is not None:
            move_vals["journal_id"] = journal.id
        move = self.env["account.move"].create(move_vals)
        return move.invoice_line_ids[:1]

    # ---- _map_account_item ------------------------------------------ #
    def test_account_item_from_account(self):
        line = self._line(account=self.income)
        self.assertEqual(self._mapper()._map_account_item(line), 9001)

    def test_account_item_falls_back_to_journal(self):
        line = self._line(account=self.income_unmapped, journal=self.journal_mapped)
        self.assertEqual(self._mapper()._map_account_item(line), 7001)

    def test_account_item_unmapped_raises(self):
        line = self._line(account=self.income_unmapped, journal=self.journal_plain)
        with self.assertRaises(MappingError):
            self._mapper()._map_account_item(line)

    # ---- _pick_freee_tax -------------------------------------------- #
    def test_pick_tax_single(self):
        line = self._line(taxes=[self.tax_a])
        self.assertEqual(
            self._mapper()._pick_freee_tax(line),
            line.tax_ids.filtered(lambda t: t.freee_tax_code),
        )

    def test_pick_tax_none_raises(self):
        line = self._line(taxes=[self.tax_nocode])
        with self.assertRaises(MappingError):
            self._mapper()._pick_freee_tax(line)

    def test_pick_tax_multiple_raises(self):
        line = self._line(taxes=[self.tax_a, self.tax_b])
        with self.assertRaises(MappingError):
            self._mapper()._pick_freee_tax(line)

    # ---- _map_item -------------------------------------------------- #
    def test_map_item_with_product(self):
        line = self._line(product=self.product_mapped)
        self.assertEqual(self._mapper()._map_item(line), 5001)

    def test_map_item_product_without_freee_item(self):
        line = self._line(product=self.product_plain)
        self.assertFalse(self._mapper()._map_item(line))

    def test_map_item_no_product(self):
        line = self._line()
        self.assertFalse(self._mapper()._map_item(line))

    # ---- _map_section ----------------------------------------------- #
    def test_map_section_with_analytic(self):
        line = self._line(analytic={str(self.analytic.id): 100})
        self.assertEqual(self._mapper()._map_section(line), 3001)

    def test_map_section_no_distribution(self):
        line = self._line()
        self.assertFalse(self._mapper()._map_section(line))

    def test_map_section_skips_non_numeric_key(self):
        # The distribution key is normally an analytic-account id; guard the
        # defensive non-numeric branch with a stub line.
        class _StubLine:
            analytic_distribution = {"not-a-number": 100}

        self.assertFalse(self._mapper()._map_section(_StubLine()))

    # ---- _map_partner ----------------------------------------------- #
    def test_map_partner_by_id(self):
        self.partner.freee_partner_id = 4242
        self.assertEqual(
            self._mapper()._map_partner(self.partner), {"partner_id": 4242}
        )

    def test_map_partner_by_code(self):
        self.partner.write({"freee_partner_id": False, "freee_partner_code": "ACME-1"})
        self.assertEqual(
            self._mapper()._map_partner(self.partner),
            {"partner_code": "ACME-1"},
        )

    def test_map_partner_unmapped_raises(self):
        self.partner.write({"freee_partner_id": False, "freee_partner_code": False})
        with self.assertRaises(MappingError):
            self._mapper()._map_partner(self.partner)

    def test_map_partner_empty_raises(self):
        with self.assertRaises(MappingError):
            self._mapper()._map_partner(self.env["res.partner"])
