# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""Operational-hardening tests.

Each test exercises one of the runtime behaviours kept in the MVP:

* paginated wizard fetch
* 401 → forced refresh → retry once
* 429 back-off cap
* warning logs on adapter errors
"""

from contextlib import contextmanager
from datetime import timedelta
from unittest import mock

from odoo import fields
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.connector.exception import NetworkRetryableError
from odoo.addons.queue_job.exception import RetryableJobError

from ..components.adapter import (
    MAX_PAGES,
    RATE_LIMIT_MAX_BACKOFF_SECONDS,
    FreeeAPIError,
)
from .common import FreeeBackendTestCommon, make_response

ADAPTER_REQUESTS = "odoo.addons.connector_freee_base.components.adapter.requests"
MODEL_REQUESTS = "odoo.addons.connector_freee_base.models.freee_backend.requests"
# Muted for the OCA checklog CI: these tests intentionally trigger adapter
# WARNING logs (401 refresh, 429 caps, network error).
ADAPTER_LOG = "odoo.addons.connector_freee_base.components.adapter"


@tagged("post_install", "-at_install")
class TestOperationalHardening(FreeeBackendTestCommon):
    def setUp(self):
        super().setUp()
        self.backend._write_secret("encrypted_access_token", "AT-test")
        self.backend._write_secret("encrypted_refresh_token", "RT-test")
        self.backend.sudo().write(
            {
                "token_expires_at": fields.Datetime.now() + timedelta(hours=1),
                "state": "authorized",
            }
        )

    @contextmanager
    def _adapter(self):
        with self.backend.work_on(self.backend._name) as work:
            yield work.component(usage="backend.adapter")

    # ------------------------------------------------------------------ #
    # 401 forces a refresh and retries once
    # ------------------------------------------------------------------ #
    @mute_logger(ADAPTER_LOG)
    def test_401_then_200_after_refresh(self):
        # Stage two HTTP responses: 401 then 200.
        responses = [
            make_response(401, json_body={"status_code": 401}),
            make_response(200, json_body={"ok": True}),
        ]
        with (
            self._adapter() as adapter,
            mock.patch(f"{ADAPTER_REQUESTS}.request", side_effect=responses) as req,
            mock.patch(f"{MODEL_REQUESTS}.post") as token_post,
        ):
            token_post.return_value = make_response(
                200,
                json_body={
                    "access_token": "AT-fresh",
                    "refresh_token": "RT-fresh",
                    "expires_in": 21600,
                },
            )
            result = adapter.get("/api/1/users/me")
        self.assertEqual(result, {"ok": True})
        # Two HTTP calls, one token refresh between them.
        self.assertEqual(req.call_count, 2)
        token_post.assert_called_once()
        # Second call carries the new bearer.
        self.assertEqual(
            req.call_args_list[1].kwargs["headers"]["Authorization"],
            "Bearer AT-fresh",
        )

    @mute_logger(ADAPTER_LOG)
    def test_double_401_surfaces_freee_api_error(self):
        # Even after refresh, freee keeps rejecting → not retryable.
        responses = [
            make_response(401, json_body={}),
            make_response(401, json_body={}),
        ]
        with (
            self._adapter() as adapter,
            mock.patch(f"{ADAPTER_REQUESTS}.request", side_effect=responses),
            mock.patch(f"{MODEL_REQUESTS}.post") as token_post,
        ):
            token_post.return_value = make_response(
                200,
                json_body={
                    "access_token": "AT-fresh",
                    "expires_in": 21600,
                },
            )
            with self.assertRaises(FreeeAPIError):
                adapter.get("/api/1/users/me")

    # ------------------------------------------------------------------ #
    # 429 back-off cap
    # ------------------------------------------------------------------ #
    @mute_logger(ADAPTER_LOG)
    def test_huge_retry_after_is_capped(self):
        with (
            self._adapter() as adapter,
            mock.patch(f"{ADAPTER_REQUESTS}.request") as req,
        ):
            req.return_value = make_response(
                429,
                json_body={"error": "daily_limit"},
                headers={"Retry-After": "86400"},  # 24 h
            )
            with self.assertRaises(RetryableJobError) as ctx:
                adapter.get("/api/1/deals")
        self.assertEqual(ctx.exception.seconds, RATE_LIMIT_MAX_BACKOFF_SECONDS)

    @mute_logger(ADAPTER_LOG)
    def test_missing_retry_after_defaults_to_600(self):
        with (
            self._adapter() as adapter,
            mock.patch(f"{ADAPTER_REQUESTS}.request") as req,
        ):
            req.return_value = make_response(429, json_body={})
            with self.assertRaises(RetryableJobError) as ctx:
                adapter.get("/api/1/deals")
        self.assertEqual(ctx.exception.seconds, 600)

    # ------------------------------------------------------------------ #
    # paginate() walks pages and stops on short
    # ------------------------------------------------------------------ #
    def test_paginate_concatenates_pages(self):
        page1 = make_response(
            200,
            json_body={"partners": [{"id": i, "name": f"P{i}"} for i in range(100)]},
        )
        page2 = make_response(
            200,
            json_body={"partners": [{"id": 100, "name": "P100"}]},
        )
        with (
            self._adapter() as adapter,
            mock.patch(
                f"{ADAPTER_REQUESTS}.request", side_effect=[page1, page2]
            ) as req,
        ):
            items = adapter.paginate(
                "/api/1/partners", "partners", params={"company_id": 1}
            )
        self.assertEqual(len(items), 101)
        # First call had offset=0, second offset=100.
        self.assertEqual(req.call_args_list[0].kwargs["params"]["offset"], 0)
        self.assertEqual(req.call_args_list[1].kwargs["params"]["offset"], 100)

    # ------------------------------------------------------------------ #
    # warning logs
    # ------------------------------------------------------------------ #
    def test_network_error_logs_warning(self):
        import requests as requests_module

        with (
            self._adapter() as adapter,
            mock.patch(f"{ADAPTER_REQUESTS}.request") as req,
            self.assertLogs(
                "odoo.addons.connector_freee_base.components.adapter",
                level="WARNING",
            ) as logs,
        ):
            req.side_effect = requests_module.exceptions.ConnectTimeout("nope")
            # The adapter wraps any ``requests.exceptions.RequestException``
            # in ``NetworkRetryableError`` so queue_job retries instead of
            # marking the job permanently failed.
            with self.assertRaises(NetworkRetryableError):
                adapter.get("/api/1/users/me")
        self.assertTrue(any("network error" in msg for msg in logs.output))

    # ------------------------------------------------------------------ #
    # fetch_list: get-vs-paginate decision and the single-GET cap warning
    # ------------------------------------------------------------------ #
    def test_fetch_list_uses_single_get_for_non_paginated(self):
        """Endpoints NOT in ``PAGINATED_LIST_KEYS`` (taxes/account_items/
        sections/walletables) accept neither offset nor limit, so
        ``fetch_list`` issues exactly ONE un-paged GET. Paging them would
        re-fetch and duplicate the whole list every iteration."""
        with (
            self._adapter() as adapter,
            mock.patch(f"{ADAPTER_REQUESTS}.request") as req,
        ):
            req.return_value = make_response(
                200, json_body={"taxes": [{"code": 1}, {"code": 2}]}
            )
            items = adapter.fetch_list("/api/1/taxes", "taxes")
        self.assertEqual(len(items), 2)
        self.assertEqual(req.call_count, 1)
        self.assertNotIn("offset", req.call_args.kwargs.get("params") or {})

    @mute_logger(ADAPTER_LOG)
    def test_fetch_list_warns_on_full_single_page(self):
        """A non-paged GET that returns a full default page (100 rows) is
        the tell-tale of a freee-side cap we did not account for; warn so
        a silently-truncated picker (the C2 bug) does not pass unnoticed."""
        with (
            self._adapter() as adapter,
            mock.patch(f"{ADAPTER_REQUESTS}.request") as req,
            self.assertLogs(ADAPTER_LOG, level="WARNING") as logs,
        ):
            req.return_value = make_response(
                200, json_body={"taxes": [{"code": i} for i in range(100)]}
            )
            items = adapter.fetch_list("/api/1/taxes", "taxes")
        self.assertEqual(len(items), 100)
        self.assertTrue(any("single" in m and "GET" in m for m in logs.output))

    @mute_logger(ADAPTER_LOG)
    def test_paginate_caps_at_max_pages(self):
        """A buggy endpoint that returns a full page forever is bounded at
        ``MAX_PAGES`` with a warning, rather than looping until it exhausts
        the worker / hammers freee. ``time.sleep`` (the soft throttle) is
        stubbed so the 200-page cap is exercised instantly."""
        full_page = make_response(200, json_body={"partners": [{"id": 1}, {"id": 2}]})
        with (
            self._adapter() as adapter,
            mock.patch(f"{ADAPTER_REQUESTS}.request", return_value=full_page) as req,
            mock.patch(f"{ADAPTER_LOG}.time.sleep"),
            self.assertLogs(ADAPTER_LOG, level="WARNING") as logs,
        ):
            items = adapter.paginate("/api/1/partners", "partners", page_size=2)
        self.assertEqual(req.call_count, MAX_PAGES)
        self.assertEqual(len(items), MAX_PAGES * 2)
        self.assertTrue(any("MAX_PAGES" in m for m in logs.output))

    # ------------------------------------------------------------------ #
    # throttle bookkeeping is best-effort and corruption-tolerant
    # ------------------------------------------------------------------ #
    def test_throttle_survives_corrupt_timestamp(self):
        """A corrupt ``last_call_at`` stamp must not break the call: the
        throttle skips the wait and overwrites the stamp with a fresh,
        parseable value."""
        from datetime import datetime

        key = f"connector_freee_base.last_call_at.{self.backend.id}"
        param = self.env["ir.config_parameter"].sudo()
        param.set_param(key, "not-a-timestamp")
        with self._adapter() as adapter:
            adapter._throttle()  # must not raise
        # Stamp was overwritten with a valid ISO timestamp.
        datetime.fromisoformat(param.get_param(key))

    def test_throttle_sleeps_when_called_too_soon(self):
        """Two calls closer together than the request interval make the
        soft throttle sleep the remaining time (bounded at 10s) so wizard
        fetches / manual syncs stay inside the freee per-app budget."""
        from datetime import datetime

        key = f"connector_freee_base.last_call_at.{self.backend.id}"
        param = self.env["ir.config_parameter"].sudo()
        param.set_param(key, datetime.utcnow().isoformat())  # "called just now"
        with (
            self._adapter() as adapter,
            mock.patch(f"{ADAPTER_LOG}.time.sleep") as sleep,
        ):
            adapter._throttle()
        sleep.assert_called_once()
        waited = sleep.call_args.args[0]
        self.assertGreater(waited, 0)
        self.assertLessEqual(waited, 10)
