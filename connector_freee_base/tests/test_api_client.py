# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from contextlib import contextmanager
from datetime import timedelta
from unittest import mock

import requests

from odoo import fields
from odoo.tools import mute_logger

from odoo.addons.connector.exception import NetworkRetryableError
from odoo.addons.connector_freee_base.components.adapter import FreeeAPIError
from odoo.addons.connector_freee_base.models.freee_backend import (
    DEFAULT_REQUEST_TIMEOUT,
    FREEE_API_VERSION,
)
from odoo.addons.queue_job.exception import RetryableJobError

from .common import FreeeBackendTestCommon, make_response

ADAPTER_REQUESTS = "odoo.addons.connector_freee_base.components.adapter.requests"
MODEL_REQUESTS = "odoo.addons.connector_freee_base.models.freee_backend.requests"
# Tests below exercise error paths that the adapter logs at WARNING; mute it
# so the OCA checklog CI (OCA_ENABLE_CHECKLOG_ODOO) does not flag expected logs.
ADAPTER_LOG = "odoo.addons.connector_freee_base.components.adapter"


class TestFreeeAdapter(FreeeBackendTestCommon):
    def setUp(self):
        super().setUp()
        self.backend._write_secret("encrypted_access_token", "AT-test")
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

    def test_get_sends_bearer_token(self):
        with (
            self._adapter() as adapter,
            mock.patch(f"{ADAPTER_REQUESTS}.request") as req,
        ):
            req.return_value = make_response(200, json_body={"ok": 1})
            result = adapter.get("/api/1/users/me")

        self.assertEqual(result, {"ok": 1})
        kwargs = req.call_args.kwargs
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer AT-test")
        self.assertEqual(req.call_args.args[0], "GET")
        self.assertTrue(req.call_args.args[1].endswith("/api/1/users/me"))

    def test_post_serializes_json_body(self):
        with (
            self._adapter() as adapter,
            mock.patch(f"{ADAPTER_REQUESTS}.request") as req,
        ):
            req.return_value = make_response(200, json_body={"deal": {"id": 7}})
            adapter.post("/api/1/deals", payload={"company_id": 1})

        # ``requests`` handles encoding when ``json=`` is passed.
        self.assertEqual(req.call_args.kwargs["json"], {"company_id": 1})

    def test_expired_token_triggers_refresh(self):
        self.backend.sudo().write(
            {"token_expires_at": fields.Datetime.now() - timedelta(minutes=1)}
        )
        self.backend._write_secret("encrypted_refresh_token", "RT-test")

        with (
            self._adapter() as adapter,
            mock.patch(f"{MODEL_REQUESTS}.post") as token_post,
            mock.patch(f"{ADAPTER_REQUESTS}.request") as req,
        ):
            token_post.return_value = make_response(
                200,
                json_body={
                    "access_token": "AT-fresh",
                    "refresh_token": "RT-fresh",
                    "expires_in": 21600,
                },
            )
            req.return_value = make_response(200, json_body={"ok": True})
            adapter.get("/api/1/users/me")

        token_post.assert_called_once()
        self.assertEqual(
            req.call_args.kwargs["headers"]["Authorization"],
            "Bearer AT-fresh",
        )

    def test_token_within_leeway_triggers_refresh(self):
        """A token that is still valid but expires inside the 300s refresh
        leeway (here +200s) is refreshed pre-emptively on the next API call,
        and the request goes out with the freshly-minted token."""
        self.backend.sudo().write(
            {"token_expires_at": fields.Datetime.now() + timedelta(seconds=200)}
        )
        self.backend._write_secret("encrypted_refresh_token", "RT-test")

        with (
            self._adapter() as adapter,
            mock.patch(f"{MODEL_REQUESTS}.post") as token_post,
            mock.patch(f"{ADAPTER_REQUESTS}.request") as req,
        ):
            token_post.return_value = make_response(
                200,
                json_body={
                    "access_token": "AT-leeway",
                    "refresh_token": "RT-leeway",
                    "expires_in": 21600,
                },
            )
            req.return_value = make_response(200, json_body={"ok": True})
            adapter.get("/api/1/users/me")

        token_post.assert_called_once()
        self.assertEqual(
            req.call_args.kwargs["headers"]["Authorization"],
            "Bearer AT-leeway",
        )

    @mute_logger(ADAPTER_LOG)
    def test_4xx_raises_freee_api_error(self):
        with (
            self._adapter() as adapter,
            mock.patch(f"{ADAPTER_REQUESTS}.request") as req,
        ):
            req.return_value = make_response(
                400, json_body={"errors": [{"message": "bad"}]}
            )
            with self.assertRaises(FreeeAPIError):
                adapter.get("/api/1/deals")

    @mute_logger(ADAPTER_LOG)
    def test_429_is_retryable(self):
        with (
            self._adapter() as adapter,
            mock.patch(f"{ADAPTER_REQUESTS}.request") as req,
        ):
            req.return_value = make_response(
                429,
                json_body={"error": "rate_limit"},
                headers={"Retry-After": "12"},
            )
            with self.assertRaises(RetryableJobError) as ctx:
                adapter.get("/api/1/deals")
        self.assertEqual(ctx.exception.seconds, 12)

    @mute_logger(ADAPTER_LOG)
    def test_5xx_is_retryable(self):
        with (
            self._adapter() as adapter,
            mock.patch(f"{ADAPTER_REQUESTS}.request") as req,
        ):
            req.return_value = make_response(503, text="boom")
            with self.assertRaises(RetryableJobError):
                adapter.get("/api/1/deals")

    @mute_logger(ADAPTER_LOG)
    def test_network_error_is_retryable(self):
        with (
            self._adapter() as adapter,
            mock.patch(f"{ADAPTER_REQUESTS}.request") as req,
        ):
            req.side_effect = requests.exceptions.ConnectionError("down")
            with self.assertRaises(NetworkRetryableError):
                adapter.get("/api/1/deals")

    # ------------------------------------------------------------------ #
    # Request shaping: API-version header, timeout fallback              #
    # ------------------------------------------------------------------ #
    def test_request_sends_api_version_header(self):
        """Every request pins freee's dated API version via the
        ``X-Api-Version`` header so a future default-version bump on
        freee's side cannot silently change response shapes."""
        with (
            self._adapter() as adapter,
            mock.patch(f"{ADAPTER_REQUESTS}.request") as req,
        ):
            req.return_value = make_response(200, json_body={"ok": 1})
            adapter.get("/api/1/users/me")
        self.assertEqual(
            req.call_args.kwargs["headers"]["X-Api-Version"], FREEE_API_VERSION
        )

    def test_request_timeout_zero_falls_back_to_default(self):
        """``request_timeout=0`` (misconfigured / unset) must not send a
        zero timeout — it falls back to ``DEFAULT_REQUEST_TIMEOUT`` so a
        request cannot hang forever."""
        self.backend.sudo().write({"request_timeout": 0})
        with (
            self._adapter() as adapter,
            mock.patch(f"{ADAPTER_REQUESTS}.request") as req,
        ):
            req.return_value = make_response(200, json_body={"ok": 1})
            adapter.get("/api/1/users/me")
        self.assertEqual(req.call_args.kwargs["timeout"], DEFAULT_REQUEST_TIMEOUT)

    # ------------------------------------------------------------------ #
    # Response decoding edge cases                                        #
    # ------------------------------------------------------------------ #
    @mute_logger(ADAPTER_LOG)
    def test_non_json_2xx_raises(self):
        """A 2xx whose body is not JSON (e.g. an HTML proxy page) raises
        FreeeAPIError rather than silently returning garbage."""
        with (
            self._adapter() as adapter,
            mock.patch(f"{ADAPTER_REQUESTS}.request") as req,
        ):
            req.return_value = make_response(200, json_body=None, text="<html/>")
            with self.assertRaises(FreeeAPIError):
                adapter.get("/api/1/users/me")

    def test_empty_2xx_returns_none(self):
        """An empty 2xx body (e.g. a 204-style DELETE) decodes to ``None``
        rather than raising."""
        with (
            self._adapter() as adapter,
            mock.patch(f"{ADAPTER_REQUESTS}.request") as req,
        ):
            req.return_value = make_response(200, json_body=None, text="")
            self.assertIsNone(adapter.get("/api/1/users/me"))

    @mute_logger(ADAPTER_LOG)
    def test_4xx_log_excludes_request_payload(self):
        """On a non-retryable 4xx the warning carries only freee's error
        structure — never the request body, which can hold partner /
        amount / line text (the H1 leak class)."""
        with (
            self._adapter() as adapter,
            mock.patch(f"{ADAPTER_REQUESTS}.request") as req,
        ):
            req.return_value = make_response(
                400, json_body={"errors": [{"message": "bad"}]}
            )
            with self.assertLogs(ADAPTER_LOG, level="WARNING") as logs:
                with self.assertRaises(FreeeAPIError):
                    adapter.post(
                        "/api/1/deals",
                        payload={"partner_id": 7777, "secret_amount": "SENSITIVE_999"},
                    )
        joined = "\n".join(logs.output)
        self.assertNotIn("SENSITIVE_999", joined)
        self.assertNotIn("partner_id", joined)
