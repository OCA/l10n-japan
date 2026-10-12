# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
import json
from datetime import timedelta
from unittest import mock

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tools import mute_logger

from odoo.addons.connector_freee_base.models.freee_backend import _safe_oauth_error

from .common import FreeeBackendTestCommon, make_response

REQUESTS_PATH = "odoo.addons.connector_freee_base.models.freee_backend.requests"


def _encode_state(backend_id, nonce):
    """Build a base64url OAuth ``state`` exactly like
    ``freee.backend._encode_state`` does, but for an arbitrary
    ``backend_id`` so tests can forge a state pointing at a
    non-existent backend.
    """
    payload = json.dumps(
        {"backend_id": backend_id, "nonce": nonce}, separators=(",", ":")
    )
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


# Muted so the OCA checklog CI does not flag the expected warnings/errors these
# error-path tests emit.
BACKEND_LOG = "odoo.addons.connector_freee_base.models.freee_backend"


class TestOAuthFlow(FreeeBackendTestCommon):
    def test_authorize_builds_url_and_stores_state(self):
        action = self.backend.action_authorize()
        self.assertEqual(action["type"], "ir.actions.act_url")
        self.assertIn("response_type=code", action["url"])
        self.assertIn("client_id=test-client-id", action["url"])
        self.assertIn("redirect_uri=", action["url"])
        self.assertTrue(self.backend.sudo().oauth_state)

    def test_authorize_requires_credentials(self):
        backend = self.env["freee.backend"].create(
            {"name": "Empty", "company_id": self.env.company.id}
        )
        with self.assertRaises(UserError):
            backend.action_authorize()

    def test_state_round_trip(self):
        encoded = self.backend._encode_state("nonce-abc")
        decoded = self.backend._decode_state(encoded)
        self.assertEqual(decoded["backend_id"], self.backend.id)
        self.assertEqual(decoded["nonce"], "nonce-abc")

    def test_resolve_callback_persists_tokens(self):
        # Prime the state first.
        self.backend.action_authorize()
        encoded = self.backend._encode_state(self.backend.sudo().oauth_state)

        token_payload = {
            "access_token": "AT-1",
            "refresh_token": "RT-1",
            "expires_in": 21600,
        }
        with mock.patch(f"{REQUESTS_PATH}.post") as post:
            post.return_value = make_response(200, json_body=token_payload)
            self.env["freee.backend"]._resolve_callback("CODE", encoded)

        # Token endpoint was hit with the right form data.
        called_with = post.call_args
        self.assertIn("public_api/token", called_with.args[0])
        self.assertEqual(called_with.kwargs["data"]["grant_type"], "authorization_code")
        self.assertEqual(called_with.kwargs["data"]["code"], "CODE")

        backend = self.backend
        self.assertEqual(backend.state, "authorized")
        self.assertEqual(backend._read_secret("encrypted_access_token"), "AT-1")
        self.assertEqual(backend._read_secret("encrypted_refresh_token"), "RT-1")
        # State nonce was cleared after successful exchange.
        self.assertFalse(backend.sudo().oauth_state)

    @mute_logger(BACKEND_LOG)
    def test_resolve_callback_rejects_bad_state(self):
        with self.assertRaises(ValidationError):
            self.env["freee.backend"]._resolve_callback("CODE", "not-a-valid-state")

    @mute_logger(BACKEND_LOG)
    def test_resolve_callback_rejects_state_mismatch(self):
        # Encode a state for an existing backend but never store the nonce.
        encoded = self.backend._encode_state("forged-nonce")
        with self.assertRaises(ValidationError):
            self.env["freee.backend"]._resolve_callback("CODE", encoded)

    def test_token_refresh_updates_expiry(self):
        backend = self.backend
        backend._write_secret("encrypted_refresh_token", "RT-old")
        backend.sudo().write(
            {
                "token_expires_at": fields.Datetime.now() - timedelta(minutes=1),
                "state": "authorized",
            }
        )
        with mock.patch(f"{REQUESTS_PATH}.post") as post:
            post.return_value = make_response(
                200,
                json_body={
                    "access_token": "AT-new",
                    "refresh_token": "RT-new",
                    "expires_in": 21600,
                },
            )
            backend._refresh_access_token()

        self.assertEqual(backend._read_secret("encrypted_access_token"), "AT-new")
        self.assertEqual(backend._read_secret("encrypted_refresh_token"), "RT-new")
        self.assertFalse(backend._is_token_expired())

    def test_refresh_without_refresh_token_raises(self):
        with self.assertRaises(UserError):
            self.backend._refresh_access_token()

    @mute_logger(BACKEND_LOG)
    def test_token_endpoint_error_marks_backend_error(self):
        # NOTE: ``assertRaises`` wraps the call in a savepoint that rolls
        # back DB writes when the expected exception fires (see
        # odoo.tests.common.BaseCase._assertRaises). Catch ``UserError``
        # manually so the ``state="error"`` write performed before the
        # raise survives for the assertion below.
        with mock.patch(f"{REQUESTS_PATH}.post") as post:
            post.return_value = make_response(
                400, json_body={"error": "bad"}, text="bad"
            )
            raised = False
            try:
                self.backend._exchange_code_for_token("CODE")
            except UserError:
                raised = True
            self.assertTrue(raised, "UserError was expected")
        self.assertEqual(self.backend.state, "error")

    # ------------------------------------------------------------------ #
    # state resolves to a non-existent backend                           #
    # ------------------------------------------------------------------ #
    @mute_logger(BACKEND_LOG)
    def test_resolve_callback_rejects_unknown_backend(self):
        """A structurally valid state whose ``backend_id`` does not exist is
        rejected with ``Unknown freee backend.``. The existence check runs
        before the nonce check, so the (bogus) nonce never matters."""
        encoded = _encode_state(999999, "any-nonce")
        # Assert the message so this cannot pass via the "Invalid OAuth
        # state." (undecodable) or "OAuth state mismatch." (bad nonce)
        # branches — it must be the unknown-backend branch specifically.
        with self.assertRaisesRegex(ValidationError, "Unknown freee backend"):
            self.env["freee.backend"]._resolve_callback("CODE", encoded)

    # ------------------------------------------------------------------ #
    # token-expiry leeway boundary (``_is_token_expired``)                #
    # ------------------------------------------------------------------ #
    def test_token_expired_within_leeway(self):
        """A token expiring inside the 300s refresh leeway is treated as
        expired, so the next API call refreshes it pre-emptively rather than
        sending a token that may lapse mid-request.

        ``_is_token_expired`` returns ``now() + 300s >= token_expires_at``.
        With an expiry 200s out, ``now+300 >= now+200`` holds (200 < the 300s
        leeway), so the token counts as expired.
        """
        self.backend.sudo().write(
            {"token_expires_at": fields.Datetime.now() + timedelta(seconds=200)}
        )
        self.assertTrue(self.backend._is_token_expired())

    def test_token_valid_outside_leeway(self):
        """Complement of :meth:`test_token_expired_within_leeway`: a token
        expiring *beyond* the 300s leeway is still valid, so no refresh is
        forced. With an expiry 400s out, ``now+300 >= now+400`` is False
        (400 > the 300s leeway). The 100s margin keeps the test stable
        against the few microseconds that elapse between the write and the
        assertion."""
        self.backend.sudo().write(
            {"token_expires_at": fields.Datetime.now() + timedelta(seconds=400)}
        )
        self.assertFalse(self.backend._is_token_expired())

    def test_missing_expiry_counts_as_expired(self):
        """An unset ``token_expires_at`` (never authorized, or cleared on
        revoke) is treated as expired — fail safe by forcing a refresh /
        surfacing the not-authorized path rather than sending a stale or
        absent token."""
        self.backend.sudo().write({"token_expires_at": False})
        self.assertTrue(self.backend._is_token_expired())

    # ------------------------------------------------------------------ #
    # token-endpoint errors are logged without leaking secrets            #
    # ------------------------------------------------------------------ #
    def test_safe_oauth_error_returns_only_code_and_description(self):
        """``_safe_oauth_error`` echoes only the OAuth ``error`` /
        ``error_description``; the raw token-endpoint body (which can carry
        ``client_secret`` / ``refresh_token``) is never included."""
        resp = make_response(
            400,
            json_body={"error": "invalid_grant", "error_description": "code expired"},
            text="client_secret=SUPER_SECRET&refresh_token=RT_LEAK",
        )
        summary = _safe_oauth_error(resp)
        self.assertEqual(summary, "invalid_grant: code expired")
        self.assertNotIn("SUPER_SECRET", summary)
        self.assertNotIn("RT_LEAK", summary)

    @mute_logger("odoo.tools.translate")
    def test_safe_oauth_error_suppresses_non_json_body(self):
        """When the body is not JSON (e.g. an HTML error page injected by a
        proxy/CDN/WAF in front of freee), it is fully suppressed rather than
        echoed into the log — we cannot assume an arbitrary body is free of
        sensitive data. Here a fake ``RT_LEAK`` token in an HTML body must
        not appear in the returned summary."""
        resp = make_response(400, json_body=None, text="<html>RT_LEAK</html>")
        self.assertNotIn("RT_LEAK", _safe_oauth_error(resp))

    @mute_logger("odoo.tools.translate")
    def test_safe_oauth_error_suppresses_non_dict_json(self):
        """A JSON body that parses but is not the expected ``{error, ...}``
        object (e.g. a bare list or string) is suppressed too — only a
        dict's ``error`` / ``error_description`` keys are ever surfaced, so
        anything else in the body cannot leak."""
        resp = make_response(400, json_body=["RT_LEAK"])
        self.assertNotIn("RT_LEAK", _safe_oauth_error(resp))

    @mute_logger(BACKEND_LOG)
    def test_token_exchange_4xx_logs_without_secrets(self):
        """End-to-end: on a 4xx token exchange the emitted ERROR log carries
        only the OAuth code/description — never the request body
        (``client_secret``) nor the raw response body (possible
        ``refresh_token``)."""
        self.backend.client_secret = "PLAINTEXT_SECRET"
        with mock.patch(f"{REQUESTS_PATH}.post") as post:
            post.return_value = make_response(
                400,
                json_body={"error": "invalid_grant", "error_description": "expired"},
                text="refresh_token=RT_LEAK client_secret=PLAINTEXT_SECRET",
            )
            with self.assertLogs(BACKEND_LOG, level="ERROR") as logs:
                with self.assertRaises(UserError):
                    self.backend._exchange_code_for_token("CODE")
        joined = "\n".join(logs.output)
        self.assertIn("invalid_grant", joined)
        self.assertNotIn("RT_LEAK", joined)
        self.assertNotIn("PLAINTEXT_SECRET", joined)

    # ------------------------------------------------------------------ #
    # export_from_date stamped once, on first authorization              #
    # ------------------------------------------------------------------ #
    def test_first_authorization_stamps_export_from_date(self):
        """The first successful authorization stamps ``export_from_date`` to
        today so the cron sweep does not retroactively export historical
        invoices; a later token refresh must not move it."""
        self.assertFalse(self.backend.export_from_date)
        with mock.patch(f"{REQUESTS_PATH}.post") as post:
            post.return_value = make_response(
                200,
                json_body={
                    "access_token": "AT",
                    "refresh_token": "RT",
                    "expires_in": 21600,
                },
            )
            self.backend._exchange_code_for_token("CODE")
        stamped = self.backend.export_from_date
        self.assertEqual(stamped, fields.Date.context_today(self.backend))

        # A subsequent refresh must NOT move the stamp.
        with mock.patch(f"{REQUESTS_PATH}.post") as post:
            post.return_value = make_response(
                200,
                json_body={
                    "access_token": "AT2",
                    "refresh_token": "RT2",
                    "expires_in": 21600,
                },
            )
            self.backend._refresh_access_token()
        self.assertEqual(self.backend.export_from_date, stamped)

    def test_authorize_requires_web_base_url(self):
        """With no ``web.base.url`` configured the redirect URI cannot be
        built, so authorization is refused before any request is made."""
        self.env["ir.config_parameter"].sudo().set_param("web.base.url", "")
        self.backend.invalidate_recordset(["redirect_uri"])
        self.assertFalse(self.backend.redirect_uri)
        # Match the message so this cannot pass via the *other* UserError
        # branch of action_authorize (missing client_id/secret) — the
        # fixture already carries credentials, but assert it explicitly.
        with self.assertRaisesRegex(UserError, "web.base.url"):
            self.backend.action_authorize()
