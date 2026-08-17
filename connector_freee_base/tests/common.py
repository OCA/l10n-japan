# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
import json
import os

from odoo import tools
from odoo.tests import tagged

from odoo.addons.component.tests.common import TransactionComponentCase

_FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

# A deterministic, valid Fernet key for the test suite. The connector
# now reads its credential-encryption key from odoo.conf only (no DB
# fallback / auto-generation), so the tests must seed one.
_TEST_ENCRYPTION_KEY = base64.urlsafe_b64encode(b"0" * 32).decode()


def load_fixture(name):
    """Return the parsed JSON of ``tests/fixtures/<name>.json``.

    These files are *verbatim* (field names/types preserved) responses
    captured from the live freee Accounting API against a freee
    development company, with list endpoints trimmed to a few records.
    Tests feed them through the mocked HTTP layer so parsing is asserted
    against real freee payloads, not hand-written approximations.
    """
    with open(os.path.join(_FIXTURE_DIR, f"{name}.json"), encoding="utf-8") as fh:
        return json.load(fh)


@tagged("post_install", "-at_install")
class FreeeBackendTestCommon(TransactionComponentCase):
    """Test base that builds a fresh freee.backend per test.

    Inherits from ``TransactionComponentCase`` so the connector component
    registry is built for the test database. Tests that call
    ``backend.work_on(...)`` would otherwise fail with
    ``RegistryNotReadyError``.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Seed the odoo.conf-only encryption key the connector requires.
        original_key = tools.config.get("connector_freee_base_encryption_key")
        tools.config["connector_freee_base_encryption_key"] = _TEST_ENCRYPTION_KEY

        def _restore_key():
            if original_key is None:
                tools.config.pop("connector_freee_base_encryption_key", None)
            else:
                tools.config["connector_freee_base_encryption_key"] = original_key

        cls.addClassCleanup(_restore_key)
        cls.env["ir.config_parameter"].sudo().set_param(
            "web.base.url", "https://example.test"
        )
        cls.backend = cls.env["freee.backend"].create(
            {
                "name": "Test Backend",
                "client_id": "test-client-id",
                "client_secret": "test-client-secret",
                "external_company_id": "1234",
            }
        )


def make_response(status_code, json_body=None, text=None, headers=None):
    """Build a minimal stand-in for ``requests.Response``."""

    class _R:
        def __init__(self):
            self.status_code = status_code
            self._json = json_body
            self.text = (
                text
                if text is not None
                else (str(json_body) if json_body is not None else "")
            )
            self.content = self.text.encode() if self.text else b""
            self.headers = headers or {}

        def json(self):
            if self._json is None:
                raise ValueError("no json body")
            return self._json

    return _R()
