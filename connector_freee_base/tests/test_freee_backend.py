# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64

from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import new_test_user
from odoo.tools import config, mute_logger

from .common import FreeeBackendTestCommon

BACKEND_LOG = "odoo.addons.connector_freee_base.models.freee_backend"


class TestFreeeBackend(FreeeBackendTestCommon):
    def test_client_secret_is_encrypted_at_rest(self):
        backend = self.backend
        # The compute returns the plain value...
        self.assertEqual(backend.client_secret, "test-client-secret")
        # ...but the stored field is ciphertext, not the plain value.
        ciphertext = backend.sudo().encrypted_client_secret
        self.assertTrue(ciphertext)
        self.assertNotEqual(ciphertext, "test-client-secret")

    def test_secret_round_trip_through_inverse(self):
        backend = self.backend
        backend.client_secret = "rotated-secret"
        backend.invalidate_recordset(["client_secret"])
        self.assertEqual(backend.client_secret, "rotated-secret")

    def test_redirect_uri_uses_base_url(self):
        self.assertEqual(
            self.backend.redirect_uri,
            "https://example.test/freee/oauth/callback",
        )

    def test_unique_name_per_company(self):
        with (
            self.assertRaises(IntegrityError),
            mute_logger("odoo.sql_db"),
            self.cr.savepoint(),
        ):
            self.env["freee.backend"].create(
                {
                    "name": "Test Backend",
                    "client_id": "another",
                    "client_secret": "another",
                }
            )

    def test_base_urls_pinned_to_freee_domain(self):
        """api_base_url / oauth_base_url must stay https on a freee
        domain so the bearer token / client secret cannot be redirected
        to an attacker host."""
        bad_values = [
            "http://api.freee.co.jp",  # not https
            "https://evil.com",  # foreign host
            "https://api.freee.co.jp.evil.com",  # suffix-spoof
            "https://evil-freee.co.jp",  # prefix-spoof
            "ftp://api.freee.co.jp",  # wrong scheme
            "",  # empty
        ]
        for value in bad_values:
            for field in ("api_base_url", "oauth_base_url"):
                with (
                    self.assertRaises(ValidationError, msg=f"{field}={value!r}"),
                    self.cr.savepoint(),
                ):
                    self.backend.write({field: value})

    def test_valid_freee_urls_accepted(self):
        # Apex and any sub-domain over https are fine.
        self.backend.write(
            {
                "api_base_url": "https://api.freee.co.jp",
                "oauth_base_url": "https://accounts.secure.freee.co.jp",
            }
        )
        self.backend.write({"api_base_url": "https://freee.co.jp"})
        self.assertEqual(self.backend.api_base_url, "https://freee.co.jp")

    def test_revoke_clears_tokens(self):
        backend = self.backend
        backend.sudo().write({"state": "authorized"})
        backend._write_secret("encrypted_access_token", "tok")
        backend._write_secret("encrypted_refresh_token", "ref")
        backend.action_revoke()
        self.assertFalse(backend.sudo().encrypted_access_token)
        self.assertFalse(backend.sudo().encrypted_refresh_token)
        self.assertEqual(backend.state, "draft")

    def test_check_lock_date_rejects_on_or_before(self):
        """invoice_date == lock_date and earlier → raise; later → ok."""
        from datetime import date

        self.backend.sudo().lock_date = "2026-04-30"
        # On lock_date → blocked (closed period includes that day).
        with self.assertRaises(UserError):
            self.backend._check_lock_date(date(2026, 4, 30))
        # Before lock_date → blocked.
        with self.assertRaises(UserError):
            self.backend._check_lock_date(date(2026, 4, 15))
        # After lock_date → fine, no exception.
        self.backend._check_lock_date(date(2026, 5, 1))

    def test_check_lock_date_disabled_when_field_empty(self):
        """No lock_date set → the guard is a no-op."""
        from datetime import date

        self.assertFalse(self.backend.lock_date)
        self.backend._check_lock_date(date(2020, 1, 1))  # would-be ancient

    def test_single_authorized_backend_per_company(self):
        """A second authorized & active backend on the same company must
        be rejected — double-posting every invoice to two freee companies
        only surfaces at month-end and is the kind of mistake the
        constraint exists to catch up front."""
        self.backend.sudo().write({"state": "authorized"})
        with (
            self.assertRaises(ValidationError),
            self.cr.savepoint(),
        ):
            self.env["freee.backend"].create(
                {
                    "name": "Second Backend",
                    "client_id": "other",
                    "client_secret": "other",
                    "state": "authorized",
                }
            )

    def test_archived_backend_does_not_block_new_authorized(self):
        """An archived (inactive) authorized backend should not block a
        new live one — that is the supported way to rotate backends."""
        self.backend.sudo().write({"state": "authorized", "active": False})
        # Should not raise.
        live = self.env["freee.backend"].create(
            {
                "name": "Replacement Backend",
                "client_id": "rep",
                "client_secret": "rep",
                "state": "authorized",
            }
        )
        self.assertTrue(live.id)

    # ------------------------------------------------------------------ #
    # Credential encryption: wrong-key decrypt fails safe                 #
    # ------------------------------------------------------------------ #
    @mute_logger(BACKEND_LOG)
    def test_decrypt_with_wrong_key_returns_false(self):
        """If the encryption key no longer matches the stored ciphertext
        (key rotated without re-encrypting), ``_read_secret`` swallows the
        decryption failure and returns ``False`` rather than crashing the
        request or leaking the secret. The exception is logged (muted here)
        but never the plaintext."""
        self.backend._write_secret("encrypted_access_token", "AT-secret")
        self.assertEqual(
            self.backend._read_secret("encrypted_access_token"), "AT-secret"
        )
        other_key = base64.urlsafe_b64encode(b"1" * 32).decode()
        original = config.get("connector_freee_base_encryption_key")
        config["connector_freee_base_encryption_key"] = other_key
        try:
            self.assertFalse(self.backend._read_secret("encrypted_access_token"))
        finally:
            config["connector_freee_base_encryption_key"] = original

    # ------------------------------------------------------------------ #
    # Field- and model-level access control                              #
    # ------------------------------------------------------------------ #
    def test_secret_fields_hidden_from_non_admin(self):
        """Credential / token fields carry ``groups=group_freee_admin`` so a
        plain ``group_freee_user`` cannot even see them in ``fields_get``
        (and therefore cannot read them)."""
        user = new_test_user(
            self.env,
            login="freee-plain-user",
            groups="connector_freee_base.group_freee_user",
        )
        gated = {
            "client_id",
            "client_secret",
            "encrypted_client_secret",
            "encrypted_access_token",
            "encrypted_refresh_token",
            "token_expires_at",
            "oauth_state",
            "debug_log_request_payload",
        }
        visible = set(self.backend.with_user(user).fields_get().keys())
        leaked = gated & visible
        self.assertFalse(leaked, f"admin-only fields visible to freee.user: {leaked}")

    def test_plain_user_cannot_access_backend(self):
        """A user with no freee group has no ACL on ``freee.backend``."""
        user = new_test_user(self.env, login="freee-none", groups="base.group_user")
        with self.assertRaises(AccessError):
            self.backend.with_user(user).read(["name"])

    def test_freee_user_is_read_only_on_backend(self):
        """``group_freee_user`` is read-only (ir.model.access): it can read
        the backend but not write/create/unlink it."""
        user = new_test_user(
            self.env,
            login="freee-readonly",
            groups="connector_freee_base.group_freee_user",
        )
        self.backend.with_user(user).read(["name"])  # read OK
        with self.assertRaises(AccessError):
            self.backend.with_user(user).write({"name": "renamed"})

    def test_credential_actions_blocked_for_non_admin(self):
        """Credential operations are gated by ``_check_admin``: a freee.user
        without the admin group gets ``AccessError`` on authorize / revoke /
        fetch-companies / test-connection."""
        user = new_test_user(
            self.env,
            login="freee-user-noadmin",
            groups="connector_freee_base.group_freee_user",
        )
        be = self.backend.with_user(user)
        for action in (
            be.action_authorize,
            be.action_revoke,
            be.action_fetch_companies,
            be.action_test_connection,
        ):
            with self.assertRaises(AccessError):
                action()

    def test_missing_encryption_key_raises(self):
        """With no ``connector_freee_base_encryption_key`` in odoo.conf,
        writing a credential cannot encrypt and fails with a clear
        UserError rather than silently generating a DB-resident key (which
        would defeat the at-rest protection)."""
        original = config.get("connector_freee_base_encryption_key")
        config.pop("connector_freee_base_encryption_key", None)
        try:
            with self.assertRaises(UserError):
                self.backend._write_secret("encrypted_access_token", "x")
        finally:
            config["connector_freee_base_encryption_key"] = original

    def test_company_record_rule_hides_other_company_backend(self):
        """The multi-company record rule (``company_id in company_ids``)
        hides a backend belonging to a company the user is not in — a
        company-A user cannot read a company-B backend."""
        company_b = self.env["res.company"].create({"name": "freee Co B"})
        backend_b = self.env["freee.backend"].create(
            {
                "name": "Backend B",
                "client_id": "b",
                "client_secret": "b",
                "company_id": company_b.id,
            }
        )
        user = new_test_user(
            self.env,
            login="freee-company-a",
            groups="connector_freee_base.group_freee_user",
        )
        # user belongs to the default (A) company, not company_b.
        with self.assertRaises(AccessError):
            backend_b.with_user(user).read(["name"])
