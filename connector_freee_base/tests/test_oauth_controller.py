# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""HTTP-level coverage for the freee OAuth callback controller
(``/freee/oauth/callback``): the freee-admin gate, the provider-error,
missing-parameter and bad-state branches, and the success redirect.
"""

import base64
import json
from unittest import mock

from odoo import tools
from odoo.tests import HttpCase, tagged
from odoo.tools import mute_logger

from .common import make_response

MODEL_REQUESTS = "odoo.addons.connector_freee_base.models.freee_backend.requests"
# Loggers that the error/bad-state branches legitimately warn on; muted in the
# negative-path tests so OCA's checklog (which fails on any WARNING) stays green.
BACKEND_LOG = "odoo.addons.connector_freee_base.models.freee_backend"
CONTROLLER_LOG = "odoo.addons.connector_freee_base.controllers.main"


@tagged("post_install", "-at_install")
class TestOAuthController(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        key = base64.urlsafe_b64encode(b"0" * 32).decode()
        original = tools.config.get("connector_freee_base_encryption_key")
        tools.config["connector_freee_base_encryption_key"] = key

        def _restore():
            if original is None:
                tools.config.pop("connector_freee_base_encryption_key", None)
            else:
                tools.config["connector_freee_base_encryption_key"] = original

        cls.addClassCleanup(_restore)
        cls.env["ir.config_parameter"].sudo().set_param(
            "web.base.url", "https://example.test"
        )
        cls.backend = cls.env["freee.backend"].create(
            {"name": "OAuth CB Test", "client_id": "cid", "client_secret": "cse"}
        )

    def test_callback_requires_freee_admin(self):
        """A logged-in user without the freee-admin group is refused."""
        self.env["res.users"].create(
            {
                "name": "Plain User",
                "login": "plain_oauth",
                "password": "plain_oauth",
                "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        self.authenticate("plain_oauth", "plain_oauth")
        resp = self.url_open("/freee/oauth/callback?code=x&state=y")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("administrators", resp.text)

    @mute_logger(CONTROLLER_LOG)
    def test_callback_reports_provider_error(self):
        self.authenticate("admin", "admin")
        resp = self.url_open("/freee/oauth/callback?error=access_denied")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("access_denied", resp.text)

    def test_callback_missing_params(self):
        self.authenticate("admin", "admin")
        resp = self.url_open("/freee/oauth/callback")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Missing OAuth", resp.text)

    def test_callback_missing_state(self):
        """Only ``code`` present (no ``state``) → rejected before any token
        exchange."""
        self.authenticate("admin", "admin")
        resp = self.url_open("/freee/oauth/callback?code=x")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Missing OAuth", resp.text)

    def test_callback_missing_code(self):
        """Only ``state`` present (no ``code``) → rejected before any token
        exchange."""
        self.authenticate("admin", "admin")
        resp = self.url_open("/freee/oauth/callback?state=y")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Missing OAuth", resp.text)

    @mute_logger(BACKEND_LOG)
    def test_callback_bad_state(self):
        self.authenticate("admin", "admin")
        resp = self.url_open("/freee/oauth/callback?code=x&state=not-a-valid-state")
        self.assertEqual(resp.status_code, 400)

    @mute_logger(BACKEND_LOG)
    def test_callback_unknown_backend(self):
        """A structurally valid state whose ``backend_id`` does not exist is
        refused at the HTTP layer with ``Unknown freee backend.``."""
        payload = json.dumps(
            {"backend_id": 999999, "nonce": "x"}, separators=(",", ":")
        )
        encoded = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
        self.authenticate("admin", "admin")
        resp = self.url_open(f"/freee/oauth/callback?code=x&state={encoded}")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Unknown freee backend", resp.text)

    def test_callback_success_authorizes_backend(self):
        self.backend.sudo().write({"oauth_state": "nonce-xyz"})
        encoded = self.backend._encode_state("nonce-xyz")
        self.authenticate("admin", "admin")
        with mock.patch(f"{MODEL_REQUESTS}.post") as token_post:
            token_post.return_value = make_response(
                200,
                json_body={
                    "access_token": "AT-cb",
                    "refresh_token": "RT-cb",
                    "expires_in": 21600,
                },
            )
            self.url_open(f"/freee/oauth/callback?code=abc&state={encoded}")
        self.backend.invalidate_recordset()
        self.assertEqual(self.backend.state, "authorized")

    def test_callback_success_without_action_redirects_to_form(self):
        """If the backend list action's external id cannot be resolved, the
        callback still authorizes and falls back to the record form URL."""
        self.backend.sudo().write({"oauth_state": "nonce-noact"})
        encoded = self.backend._encode_state("nonce-noact")
        # Drop the action's external id so request.env.ref(...) returns
        # nothing, exercising the form-redirect fallback branch.
        self.env["ir.model.data"].search(
            [
                ("module", "=", "connector_freee_base"),
                ("name", "=", "action_freee_backend"),
            ]
        ).unlink()
        self.authenticate("admin", "admin")
        with mock.patch(f"{MODEL_REQUESTS}.post") as token_post:
            token_post.return_value = make_response(
                200,
                json_body={
                    "access_token": "AT-noact",
                    "refresh_token": "RT-noact",
                    "expires_in": 21600,
                },
            )
            resp = self.url_open(f"/freee/oauth/callback?code=abc&state={encoded}")
        self.assertEqual(resp.status_code, 200)
        self.backend.invalidate_recordset()
        self.assertEqual(self.backend.state, "authorized")
