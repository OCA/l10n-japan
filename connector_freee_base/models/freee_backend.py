# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
import json
import logging
import secrets
from datetime import timedelta
from urllib.parse import urlencode, urlparse

import requests

from odoo import SUPERUSER_ID, _, api, fields, models, tools
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)

DEFAULT_OAUTH_BASE_URL = "https://accounts.secure.freee.co.jp"
DEFAULT_API_BASE_URL = "https://api.freee.co.jp"
# The OAuth/API base URLs are operator-editable, but a value pointing
# off freee would ship the live access token / client secret to a
# non-freee host. Pin both to https on the freee domain (apex or any
# sub-domain) and reject anything else.
FREEE_URL_DOMAIN = "freee.co.jp"
TOKEN_REFRESH_LEEWAY_SECONDS = 300
DEFAULT_REQUEST_TIMEOUT = 30

# Seconds between successive freee export jobs. freee's Accounting API
# enforces ~3,600 requests/hour/app/company (~1 req/s steady-state); a
# 2 s gap leaves headroom for retries and other API calls in the same app.
# Lives in base so every freee feature module that fans out throttled
# jobs shares one rate-limit budget.
_REQUEST_INTERVAL_SECONDS = 2

# freee Accounting API version pinned in the ``X-Api-Version`` header
# on every request. Centralised here so a future API bump is a single
# edit and so feature modules can reference the same value if they need
# to.
FREEE_API_VERSION = "2020-06-15"

# queue_job channel every freee export job is dispatched on. ETA
# staggering only controls *when* a job becomes eligible; without a
# dedicated, capacity-capped channel the workers still run several in
# parallel and undo the staggering. Naming the channel here lets the
# documented hard deployment step ("[queue_job] channels = root:1,
# root.freee:1") actually bind to these jobs — before this was set the
# cap matched nothing. Shared across feature modules so one capacity
# limit governs the whole freee app/company rate-limit budget.
FREEE_QUEUE_CHANNEL = "root.freee"

# NOTE on consumption-tax rounding and the tax-accounting method
# (tax-inclusive vs tax-exclusive): intentionally NOT modelled. The
# invoice exporter computes the consumption tax itself (using
# account_tax_rounding_method on the Odoo side) and sends
# ``details[].vat`` explicitly together with the tax-inclusive
# ``details[].amount``. freee stores both values as sent, so the freee
# company's rounding / accounting-method settings do not change the
# resulting deal. No setting, capture or pre-flight check is needed for
# either.


def _safe_oauth_error(response):
    """Return a log-safe one-line summary of a freee token-endpoint error.

    The token endpoint is the only request whose *body* carries
    ``client_id`` / ``client_secret`` / ``refresh_token``. freee's error
    payload is normally ``{"error": ..., "error_description": ...}`` and
    does not echo the secret, but we still never log the raw body — only
    the OAuth error code and description, which is exactly what an
    operator needs to act (e.g. ``invalid_grant`` → re-authorize) and
    nothing else.
    """
    try:
        data = response.json()
    except ValueError:
        return _("(non-JSON error body suppressed)")
    if not isinstance(data, dict):
        return _("(error body suppressed)")
    code = data.get("error") or "?"
    desc = data.get("error_description") or ""
    return (f"{code}: {desc}".strip()).strip(":").strip()


class FreeeBackend(models.Model):
    _name = "freee.backend"
    _inherit = ["connector.backend", "mail.thread", "mail.activity.mixin"]
    _description = "freee Backend"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    state = fields.Selection(
        [
            ("draft", "Not Authorized"),
            ("authorized", "Authorized"),
            ("error", "Error"),
        ],
        default="draft",
        required=True,
        readonly=True,
        copy=False,
    )
    debug_log_request_payload = fields.Boolean(
        string="Debug: log request payload",
        default=False,
        copy=False,
        groups="connector_freee_base.group_freee_admin",
        help="Developer / troubleshooting only — keep OFF in production.\n"
        "When ON, each freee export/delete job's Result (Settings → "
        "Technical → Queue Job) additionally contains the full request "
        "payload sent to freee and freee's raw response. Those carry "
        "partner, amounts and per-line text into the UNENCRYPTED, "
        "broadly-readable queue.job.result column — the exposure the "
        "connector deliberately avoids by default (see readme/SECURITY.md, "
        "H1). Remember to turn it OFF again after troubleshooting.",
    )

    oauth_base_url = fields.Char(
        string="OAuth Base URL",
        default=DEFAULT_OAUTH_BASE_URL,
        required=True,
    )
    api_base_url = fields.Char(
        string="API Base URL",
        default=DEFAULT_API_BASE_URL,
        required=True,
    )
    client_id = fields.Char(
        string="Client ID",
        groups="connector_freee_base.group_freee_admin",
    )
    # Stored ciphertext only. Plain values are exposed via the *_secret*
    # compute fields, gated by the freee admin group.
    encrypted_client_secret = fields.Char(
        groups="connector_freee_base.group_freee_admin",
        copy=False,
    )
    encrypted_access_token = fields.Char(
        groups="connector_freee_base.group_freee_admin",
        copy=False,
    )
    encrypted_refresh_token = fields.Char(
        groups="connector_freee_base.group_freee_admin",
        copy=False,
    )
    client_secret = fields.Char(
        compute="_compute_client_secret",
        inverse="_inverse_client_secret",
        groups="connector_freee_base.group_freee_admin",
    )
    token_expires_at = fields.Datetime(
        readonly=True,
        copy=False,
        groups="connector_freee_base.group_freee_admin",
    )
    external_company_id = fields.Integer(
        string="freee Company ID",
        help="The freee 'company_id' bound to this backend. "
        "Required by most /api/1/* endpoints.",
    )
    external_company_name = fields.Char(
        string="freee Company",
        readonly=True,
        copy=False,
        help="Human-readable company name reported by freee. "
        "Populated by the Fetch Company IDs wizard.",
    )
    export_from_date = fields.Date(
        string="Export From",
        copy=False,
        help="Cron sweep only enqueues posted invoices whose "
        "``invoice_date`` is on or after this date. Stamped to today "
        "the first time the backend transitions to ``authorized`` so a "
        "fresh install does not retroactively flood freee with every "
        "historical invoice. Admin-editable for back-dated catch-up.",
    )
    lock_date = fields.Date(
        string="freee Lock Date",
        copy=False,
        help="Last day of the most recent closed (locked) period on "
        "freee — a monthly or year-end close. Invoices whose "
        "``invoice_date`` "
        "is on or before this date are skipped by the cron sweep, and "
        "the manual *Sync to freee* button raises a clear error instead "
        "of letting freee reject the request. Leave empty to disable "
        "the check.",
    )
    oauth_state = fields.Char(
        copy=False,
        readonly=True,
        groups="connector_freee_base.group_freee_admin",
    )
    redirect_uri = fields.Char(
        compute="_compute_redirect_uri",
        help="Redirect URI to register in the freee developer console.",
    )
    request_timeout = fields.Integer(
        default=DEFAULT_REQUEST_TIMEOUT,
        help="HTTP request timeout in seconds. A value of 0 falls back "
        "to the connector default at call time.",
    )

    _sql_constraints = [
        (
            "name_company_uniq",
            "unique(name, company_id)",
            "freee Backend name must be unique per company.",
        )
    ]

    @api.constrains("state", "company_id", "active")
    def _check_single_authorized_per_company(self):
        """At most one ``state='authorized'`` & ``active=True`` backend
        per company. Without this, a misconfigured 'test' backend left
        active next to the production one would have the invoice cron
        fan every posted invoice out to both freee companies — visible only
        when month-end reconciliation flags the duplicate deals.
        """
        for backend in self:
            if backend.state != "authorized" or not backend.active:
                continue
            dup = self.sudo().search_count(
                [
                    ("id", "!=", backend.id),
                    ("company_id", "=", backend.company_id.id),
                    ("state", "=", "authorized"),
                    ("active", "=", True),
                ]
            )
            if dup:
                raise ValidationError(
                    _(
                        "Company %(company)s already has an authorized & "
                        "active freee backend. Archive or revoke the other "
                        "backend before authorizing this one — keeping both "
                        "live would double-post every invoice to freee."
                    )
                    % {"company": backend.company_id.display_name}
                )

    # ------------------------------------------------------------------ #
    # Computed fields                                                    #
    # ------------------------------------------------------------------ #
    @api.depends("encrypted_client_secret")
    def _compute_client_secret(self):
        for backend in self:
            backend.client_secret = backend._read_secret("encrypted_client_secret")

    def _inverse_client_secret(self):
        for backend in self:
            current = backend._read_secret("encrypted_client_secret")
            new = backend.client_secret or False
            if current != new:
                backend._write_secret("encrypted_client_secret", new)

    @api.depends_context("uid")
    def _compute_redirect_uri(self):
        base_url = (
            self.env["ir.config_parameter"].sudo().get_param("web.base.url", default="")
        )
        for backend in self:
            backend.redirect_uri = (
                f"{base_url.rstrip('/')}/freee/oauth/callback" if base_url else False
            )

    @api.constrains("api_base_url", "oauth_base_url")
    def _check_base_urls(self):
        """Pin the freee endpoints to https on the freee domain.

        Both fields are editable by a freee admin. Left unvalidated, an
        admin (or anything that can write the record) could repoint
        ``api_base_url`` to an attacker host — every subsequent call
        ships ``Authorization: Bearer <live token>`` there — or
        ``oauth_base_url`` to exfiltrate the client secret / refresh
        token via the token POST. Accept only ``https://`` on
        ``freee.co.jp`` or any ``*.freee.co.jp`` sub-domain; reject
        everything else so the bearer token cannot leave freee.
        """
        suffix = "." + FREEE_URL_DOMAIN
        for backend in self:
            for label, value in (
                (_("API Base URL"), backend.api_base_url),
                (_("OAuth Base URL"), backend.oauth_base_url),
            ):
                parsed = urlparse((value or "").strip())
                host = parsed.hostname or ""
                if parsed.scheme != "https" or not (
                    host == FREEE_URL_DOMAIN or host.endswith(suffix)
                ):
                    raise ValidationError(
                        _(
                            "%(label)s must be an https:// URL on a freee "
                            "domain (e.g. https://api.freee.co.jp or "
                            "https://accounts.secure.freee.co.jp). Pointing "
                            "it elsewhere would send the freee access token "
                            "or client secret to a non-freee host. Got: "
                            "%(value)s"
                        )
                        % {"label": label, "value": value or _("(empty)")}
                    )

    # ------------------------------------------------------------------ #
    # Encryption helpers                                                 #
    # ------------------------------------------------------------------ #
    def _get_fernet(self):
        """Return a Fernet instance derived from the configured key.

        The key is read from ``odoo.conf`` under
        ``connector_freee_base_encryption_key``. Keeping it in the
        config file (not the DB) means it never lands in a ``pg_dump``
        and rotating it is a config edit + restart. Raise a clear error
        if it is missing rather than silently generating one — an
        auto-generated DB key would defeat the at-rest protection.
        """
        # Imported lazily so unit tests that patch the symbol can replace it.
        from cryptography.fernet import Fernet

        conf_key = tools.config.get("connector_freee_base_encryption_key")
        if not conf_key:
            raise UserError(
                _(
                    "freee credential encryption key is not configured. Add "
                    "'connector_freee_base_encryption_key = <Fernet key>' to "
                    "odoo.conf (generate one with "
                    '`python -c "from cryptography.fernet import Fernet; '
                    'print(Fernet.generate_key().decode())"`) and restart.'
                )
            )
        return Fernet(str(conf_key).strip().encode())

    def _read_secret(self, field_name):
        self.ensure_one()
        ciphertext = self[field_name]
        if not ciphertext:
            return False
        try:
            return self._get_fernet().decrypt(ciphertext.encode()).decode()
        except Exception:
            _logger.exception("Failed to decrypt %s on backend %s", field_name, self.id)
            return False

    def _write_secret(self, field_name, plain_value):
        self.ensure_one()
        if plain_value:
            ciphertext = self._get_fernet().encrypt(plain_value.encode()).decode()
        else:
            ciphertext = False
        # Write the *encrypted* column directly (its inverse lives on the
        # plain compute field, so no compute/inverse round-trip happens);
        # sudo() because the encrypted_* fields are gated behind the freee
        # admin group and this helper also runs from the OAuth callback.
        self.sudo().write({field_name: ciphertext})

    # ------------------------------------------------------------------ #
    # OAuth 2.0 — Authorization Code flow                                #
    # ------------------------------------------------------------------ #
    def _check_admin(self):
        if not self.env.user.has_group("connector_freee_base.group_freee_admin"):
            raise AccessError(_("Only freee administrators may manage credentials."))

    def action_authorize(self):
        """Build the authorize URL and open it in a new browser tab."""
        self.ensure_one()
        self._check_admin()
        if not (self.client_id and self.client_secret):
            raise UserError(_("Set Client ID and Client Secret before authorizing."))
        if not self.redirect_uri:
            raise UserError(_("System parameter 'web.base.url' is not configured."))
        state = secrets.token_urlsafe(32)
        self.sudo().write({"oauth_state": state})
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "state": self._encode_state(state),
        }
        url = f"{self.oauth_base_url.rstrip('/')}/public_api/authorize?" + urlencode(
            params
        )
        return {"type": "ir.actions.act_url", "url": url, "target": "new"}

    def _encode_state(self, nonce):
        """Encode backend id + nonce so the callback can resolve us back."""
        self.ensure_one()
        payload = json.dumps(
            {"backend_id": self.id, "nonce": nonce}, separators=(",", ":")
        )
        return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")

    @api.model
    def _decode_state(self, encoded):
        try:
            padded = encoded + "=" * (-len(encoded) % 4)
            return json.loads(base64.urlsafe_b64decode(padded.encode()))
        except (ValueError, TypeError):
            return None

    @api.model
    def _resolve_callback(self, code, encoded_state):
        """Called from the OAuth callback controller."""
        decoded = self._decode_state(encoded_state)
        if not decoded:
            _logger.warning("freee OAuth callback: undecodable state parameter")
            raise ValidationError(_("Invalid OAuth state."))
        backend = self.sudo().browse(decoded.get("backend_id"))
        if not backend.exists():
            _logger.warning(
                "freee OAuth callback: unknown backend id=%s",
                decoded.get("backend_id"),
            )
            raise ValidationError(_("Unknown freee backend."))
        if not backend.oauth_state or backend.oauth_state != decoded.get("nonce"):
            _logger.warning(
                "freee OAuth callback: state mismatch on backend %s", backend.id
            )
            raise ValidationError(_("OAuth state mismatch."))
        backend._exchange_code_for_token(code)
        backend.sudo().write({"oauth_state": False})
        return backend

    def _exchange_code_for_token(self, code):
        self.ensure_one()
        # sudo() so the call works even when triggered by a non-admin user
        # (the credentials are gated behind the freee admin group).
        backend_su = self.sudo()
        response = requests.post(
            f"{backend_su.oauth_base_url.rstrip('/')}/public_api/token",
            data={
                "grant_type": "authorization_code",
                "client_id": backend_su.client_id,
                "client_secret": backend_su.client_secret,
                "code": code,
                "redirect_uri": backend_su.redirect_uri,
            },
            timeout=backend_su.request_timeout or DEFAULT_REQUEST_TIMEOUT,
        )
        self._store_token_response(response)

    def _refresh_access_token(self):
        self.ensure_one()
        backend_su = self.sudo()
        refresh_token = backend_su._read_secret("encrypted_refresh_token")
        if not refresh_token:
            raise UserError(_("No refresh token stored — re-authorize the backend."))
        response = requests.post(
            f"{backend_su.oauth_base_url.rstrip('/')}/public_api/token",
            data={
                "grant_type": "refresh_token",
                "client_id": backend_su.client_id,
                "client_secret": backend_su.client_secret,
                "refresh_token": refresh_token,
            },
            timeout=backend_su.request_timeout or DEFAULT_REQUEST_TIMEOUT,
        )
        self._store_token_response(response)

    def _store_token_response(self, response):
        self.ensure_one()
        if response.status_code != 200:
            self.sudo().write({"state": "error"})
            # Never log response.text here: this is the token endpoint,
            # whose request body carries the client secret / refresh
            # token. Log only the OAuth error code/description.
            _logger.error(
                "freee token endpoint returned HTTP %s (%s)",
                response.status_code,
                _safe_oauth_error(response),
            )
            raise UserError(
                _("freee authentication failed (HTTP %s).") % response.status_code
            )
        payload = response.json()
        access_token = payload.get("access_token")
        refresh_token = payload.get("refresh_token")
        expires_in = int(payload.get("expires_in") or 0)
        if not access_token:
            raise UserError(_("freee did not return an access token."))
        self._write_secret("encrypted_access_token", access_token)
        if refresh_token:
            self._write_secret("encrypted_refresh_token", refresh_token)
        vals = {
            "token_expires_at": fields.Datetime.now()
            + timedelta(seconds=expires_in or 21600),
            "state": "authorized",
        }
        # Stamp the export start date the very first time we authorise so
        # the cron sweep does not retroactively grab every historical
        # invoice. Admin-editable afterwards for an intentional catch-up.
        if not self.sudo().export_from_date:
            vals["export_from_date"] = fields.Date.context_today(self)
        self.sudo().write(vals)

    # ------------------------------------------------------------------ #
    # lock_date (closing-date) guard                                      #
    # ------------------------------------------------------------------ #
    def _check_lock_date(self, issue_date):
        """Raise if ``issue_date`` falls on or before this backend's lock_date.

        freee rejects edits and deletes on transactions whose issue_date
        is inside a closed (locked) period, so attempting a POST / PUT /
        DELETE there ends in a generic 4xx the operator has to debug from
        the freee side. Stop it locally instead — the binding flips to
        ``sync_state='error'`` with a clear message.
        """
        self.ensure_one()
        if not self.lock_date or not issue_date:
            return
        if issue_date <= self.lock_date:
            raise UserError(
                _(
                    "Invoice issue date %(issue)s is on or before the freee "
                    "lock date %(lock)s for backend '%(backend)s'. freee will "
                    "not accept changes inside a closed period — adjust the "
                    "lock_date on the backend (or reverse the invoice in a "
                    "post-lock period) before retrying."
                )
                % {
                    "issue": issue_date,
                    "lock": self.lock_date,
                    "backend": self.name,
                }
            )

    # ------------------------------------------------------------------ #
    # Token access — used by the API client                              #
    # ------------------------------------------------------------------ #
    def _is_token_expired(self):
        self.ensure_one()
        if not self.token_expires_at:
            return True
        leeway = timedelta(seconds=TOKEN_REFRESH_LEEWAY_SECONDS)
        return fields.Datetime.now() + leeway >= self.token_expires_at

    def _get_access_token(self):
        """Return a non-expired access token, refreshing if needed.

        Token refresh is serialized at the deployment level, not in
        code: every freee export job runs on the capacity-capped
        ``root.freee`` queue_job channel (configured ``root.freee:1``),
        so at most one worker refreshes at a time and freee's
        refresh-token rotation never races.
        """
        self.ensure_one()
        backend_su = self.sudo()
        if backend_su._is_token_expired():
            backend_su._refresh_access_token()
        token = backend_su._read_secret("encrypted_access_token")
        if not token:
            raise UserError(_("freee backend %s is not authorized.") % backend_su.name)
        return token

    def action_fetch_companies(self):
        """Open a wizard listing companies returned by ``/api/1/companies``.

        This is the way users discover their freee ``company_id`` — the
        value is not exposed in the freee web UI.
        """
        self.ensure_one()
        self._check_admin()
        if self.state != "authorized":
            raise UserError(_("Authorize the backend before fetching companies."))
        with self.work_on(self._name) as work:
            adapter = work.component(usage="backend.adapter")
            # ``/api/1/companies`` returns the small fixed list of
            # companies this freee user belongs to — no pagination needed
            # (the get-vs-paginate decision lives in the adapter's
            # PAGINATED_LIST_KEYS, C2). Wizard creation below is atomic.
            companies = adapter.fetch_list("/api/1/companies", "companies")
        if not companies:
            raise UserError(
                _("freee returned no companies for the authorized account.")
            )
        wizard = self.env["freee.company.fetch.wizard"].create(
            {
                "backend_id": self.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "external_id": str(company.get("id")),
                            "name": company.get("name") or "",
                            "name_kana": company.get("name_kana") or False,
                            "display_name": company.get("display_name") or False,
                            "role": company.get("role") or False,
                        },
                    )
                    for company in companies
                    if company.get("id") is not None
                ],
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Select freee Company"),
            "res_model": "freee.company.fetch.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_test_connection(self):
        self.ensure_one()
        self._check_admin()
        if not self.external_company_id:
            raise UserError(
                _("Set the freee Company ID before testing the connection.")
            )
        with self.work_on(self._name) as work:
            adapter = work.component(usage="backend.adapter")
            adapter.get(f"/api/1/companies/{self.external_company_id}")
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("freee"),
                "message": _("Connection successful."),
                "type": "success",
                "sticky": False,
            },
        }

    def action_revoke(self):
        self.ensure_one()
        self._check_admin()
        # Clear ``export_from_date`` too so the next authorize cycle
        # re-stamps it to today (see ``_store_token_response``). Without
        # this, revoking and re-authorizing weeks later would have the
        # cron retroactively sweep every invoice issued during the
        # revoke window.
        self.sudo().write(
            {
                "encrypted_access_token": False,
                "encrypted_refresh_token": False,
                "token_expires_at": False,
                "oauth_state": False,
                "state": "draft",
                "export_from_date": False,
            }
        )

    # ------------------------------------------------------------------ #
    # Admin notification — generic, one open activity per (backend, type) #
    # ------------------------------------------------------------------ #
    def _notify_freee_admins(self, activity_xmlid, summary, note):
        """Schedule a deduplicated to-do for every freee admin.

        Used for operational alerts that must not pile up under a
        frequently-running cron (aggregate export failures, ...): at most
        one open activity of ``activity_xmlid`` per backend. Paired with
        :meth:`_clear_freee_admin_activities`, which retracts it once the
        condition clears.
        """
        self.ensure_one()
        activity_type = self.env.ref(activity_xmlid, raise_if_not_found=False)
        if not activity_type:
            return
        already_open = (
            self.env["mail.activity"]
            .sudo()
            .search_count(
                [
                    ("res_model", "=", self._name),
                    ("res_id", "=", self.id),
                    ("activity_type_id", "=", activity_type.id),
                ]
            )
        )
        if already_open:
            return
        admin_group = self.env.ref(
            "connector_freee_base.group_freee_admin", raise_if_not_found=False
        )
        if not admin_group:
            return
        admins = admin_group.users.filtered(
            lambda user: user.active and not user.share and user.id != SUPERUSER_ID
        )
        for admin in admins:
            self.sudo().activity_schedule(
                activity_xmlid,
                user_id=admin.id,
                summary=summary,
                note=note,
            )
        # Push the alert, not just a silent to-do: post it to the
        # backend's chatter addressed to every freee admin so Odoo
        # delivers it via Inbox + email per each admin's notification
        # settings (mail.thread is the framework's native push channel —
        # no extra Slack/webhook wiring). Reached only when the activity
        # above was newly scheduled (the dedup early-return guards it), so
        # a frequently-running cron pushes exactly once per occurrence.
        # message_post never raises into the sweep, but isolate it so a
        # mail mis-config can't stop the to-do/escalation path.
        partner_ids = admins.partner_id.ids
        if partner_ids:
            try:
                self.sudo().message_post(
                    body=note,
                    subject=summary,
                    partner_ids=partner_ids,
                    message_type="notification",
                    subtype_xmlid="mail.mt_comment",
                )
            except Exception:  # noqa: BLE001 — alerting must not break the sweep
                _logger.exception(
                    "freee: failed to push admin notification for backend %s",
                    self.id,
                )

    def _clear_freee_admin_activities(self, activity_xmlid):
        """Retract any open admin to-dos of ``activity_xmlid``."""
        self.ensure_one()
        activity_type = self.env.ref(activity_xmlid, raise_if_not_found=False)
        if not activity_type:
            return
        self.env["mail.activity"].sudo().search(
            [
                ("res_model", "=", self._name),
                ("res_id", "=", self.id),
                ("activity_type_id", "=", activity_type.id),
            ]
        ).unlink()
