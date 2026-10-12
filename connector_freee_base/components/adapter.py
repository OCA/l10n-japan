# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging
import time
from datetime import datetime

import requests

from odoo import _
from odoo.exceptions import UserError

from odoo.addons.component.core import AbstractComponent
from odoo.addons.connector.exception import NetworkRetryableError
from odoo.addons.queue_job.exception import RetryableJobError

from ..models.freee_backend import (
    _REQUEST_INTERVAL_SECONDS,
    DEFAULT_REQUEST_TIMEOUT,
    FREEE_API_VERSION,
)

_logger = logging.getLogger(__name__)

# Namespace for the PostgreSQL advisory session lock that serialises
# rate-limit bookkeeping per backend. This is the only advisory lock
# the connector takes (token refresh is serialised by the capacity-
# capped ``root.freee`` queue_job channel, not a lock); the value is
# ASCII "free" + 1, leaving the plain "free" namespace available if a
# future lock is ever needed.
_RATE_LIMIT_LOCK_NS = 0x66726565 + 1
# Hard cap on the wait imposed by the runtime throttle. The
# ``root.freee:1`` channel cap is the primary serialiser; this is a
# belt-and-suspenders so wizard fetches and manual *Sync to freee*
# clicks (which run outside the channel) also respect the freee
# per-app rate budget. Bail out instead of pinning a worker for
# minutes.
_RATE_LIMIT_MAX_SLEEP_SECONDS = 10

RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}

# Hard cap on ``Retry-After`` echoed back by freee on 429. Above this
# the request is almost certainly hitting a daily limit, not an
# instantaneous burst — falling for the literal header value would
# park a queue_job worker for hours. Honoured up to this ceiling
# and then we cap so queue_job retries on a sane cadence; the cron
# will catch up the same night.
RATE_LIMIT_MAX_BACKOFF_SECONDS = 3600

# Default page size for the paginated wizard fetches. freee's
# ``/api/1/*`` master-data endpoints page at 100 by default but accept
# up to 100; ask for the documented maximum explicitly so we surface
# the full picker list in as few HTTP round-trips as possible.
DEFAULT_PAGE_LIMIT = 100

# How many pages we will follow before stopping with a warning.
# A runaway loop (e.g. a freee bug that returns full pages forever)
# would otherwise hammer their API and exhaust queue_job workers.
MAX_PAGES = 200

# Which freee list endpoints page on ``offset`` + ``limit``, keyed by
# the JSON envelope key that holds the rows. This is the single source
# of truth for the get-vs-paginate decision (consumed by
# :meth:`FreeeAdapter.fetch_list`) so individual wizards never have to
# re-derive it from the freee OpenAPI spec. Keys absent here belong to
# endpoints that accept neither ``offset`` nor ``limit`` and return
# their full list in one response (``account_items``, ``sections``,
# ``walletables``, ``taxes``); paging those re-fetches and duplicates
# the whole list up to :data:`MAX_PAGES`.
PAGINATED_LIST_KEYS = frozenset({"partners", "items", "deals"})


class FreeeAPIError(UserError):
    """Raised when the freee API returns an unrecoverable error."""


class FreeeAdapter(AbstractComponent):
    """Generic freee REST API client (abstract base).

    Concrete adapters (e.g. ``freee.backend.adapter`` for general
    fetch wizards, ``freee.account.move.adapter`` for /deals) inherit
    this component and call :meth:`get`, :meth:`post`, :meth:`put`,
    :meth:`delete`. The adapter automatically:

    * injects an OAuth Bearer token, refreshing it transparently when
      the stored token has expired *or* when freee returns 401 on a
      request the caller already had a token for;
    * decodes JSON responses;
    * raises :class:`FreeeAPIError` for unrecoverable HTTP errors and
      :class:`RetryableJobError` for transient ones (429, 5xx,
      network);
    * exposes :meth:`fetch_list` so wizards pull a complete list
      endpoint without each one re-deciding get-vs-paginate or
      re-inventing the ``offset``/``limit`` loop.
    """

    _name = "freee.adapter"
    _inherit = "base.freee.connector"
    _usage = "backend.adapter"

    # ------------------------------------------------------------------ #
    # Public verbs                                                       #
    # ------------------------------------------------------------------ #
    def get(self, path, params=None):
        """Issue an authenticated ``GET`` and return the decoded JSON."""
        return self._call("GET", path, params=params)

    def post(self, path, payload=None, params=None):
        """Issue an authenticated ``POST`` with a JSON body."""
        return self._call("POST", path, params=params, json_body=payload)

    def put(self, path, payload=None, params=None):
        """Issue an authenticated ``PUT`` with a JSON body."""
        return self._call("PUT", path, params=params, json_body=payload)

    def delete(self, path, params=None):
        """Issue an authenticated ``DELETE``."""
        return self._call("DELETE", path, params=params)

    def paginate(self, path, list_key, params=None, page_size=DEFAULT_PAGE_LIMIT):
        """GET every page of a freee list endpoint and yield items.

        Only the freee endpoints that accept ``offset`` + ``limit``
        (``/api/1/partners``, ``/api/1/items``, ``/api/1/deals``) may be
        paged through here; firing one un-paged GET against them would
        silently drop everything past the 100-row default. The
        master-data endpoints that do NOT accept ``offset``/``limit``
        (``/api/1/account_items``, ``/api/1/sections``,
        ``/api/1/walletables``, ``/api/1/taxes``) return their full list
        in a single response and must call :meth:`get` directly — paging
        them re-fetches the whole list each iteration and duplicates
        every row up to :data:`MAX_PAGES`.

        Walks pages until a short page comes back, capped at
        :data:`MAX_PAGES`. Returns a Python list — wizards consume the
        whole result to populate ``line_ids``, so streaming would not
        help.
        """
        items = []
        for page in range(MAX_PAGES):
            merged = dict(params or {})
            merged["offset"] = page * page_size
            merged["limit"] = page_size
            payload = self.get(path, params=merged) or {}
            chunk = payload.get(list_key) or []
            items.extend(chunk)
            if len(chunk) < page_size:
                return items
        _logger.warning(
            "freee.paginate: hit MAX_PAGES=%s on %s; truncating at %s rows",
            MAX_PAGES,
            path,
            len(items),
        )
        return items

    def fetch_list(self, path, list_key, params=None):
        """Fetch a complete freee list, paging or not per endpoint metadata.

        Wizards call this instead of choosing :meth:`get` vs
        :meth:`paginate` by hand: the get-vs-paginate decision lives in
        one place (:data:`PAGINATED_LIST_KEYS`) keyed by ``list_key``
        (the JSON envelope key holding the rows, e.g. ``"partners"``).
        Endpoints that page are walked page by page; the rest are issued
        as a single GET because they accept neither ``offset`` nor
        ``limit`` and return everything in one response.

        For the single-GET endpoints we have no page loop to tell us the
        list was complete, so warn if the response is as large as a full
        default page: that is the tell-tale of a freee-side cap we have
        not accounted for, and silently dropping rows from the picker is
        exactly the C2 bug. Returns a Python list.
        """
        if list_key in PAGINATED_LIST_KEYS:
            return self.paginate(path, list_key, params=params)
        payload = self.get(path, params=params) or {}
        items = payload.get(list_key) or []
        if len(items) >= DEFAULT_PAGE_LIMIT:
            _logger.warning(
                "freee.fetch_list: %s returned %s rows from a single "
                "un-paged GET; if freee silently capped the response some "
                "%s are missing from the wizard. Verify the list is "
                "complete against freee.",
                path,
                len(items),
                list_key,
            )
        return items

    # ------------------------------------------------------------------ #
    # Internals                                                          #
    # ------------------------------------------------------------------ #
    def _build_url(self, path):
        backend = self.backend_record
        base = backend.api_base_url.rstrip("/")
        return f"{base}/{path.lstrip('/')}"

    def _build_headers(self):
        backend = self.backend_record
        token = backend._get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Api-Version": FREEE_API_VERSION,
        }

    def _throttle(self):
        """Soft per-backend request spacing.

        The nightly cron staggers jobs with ``eta`` and a
        ``root.freee:1`` channel cap, which already keeps the queue
        side well inside the freee per-app budget. Wizard fetches and
        manual *Sync to freee* clicks run outside that channel,
        though, and a burst of them can still trigger 429s. Track the
        last call timestamp in ``ir.config_parameter`` (one row per
        backend) and sleep up to
        :data:`_RATE_LIMIT_MAX_SLEEP_SECONDS` so successive calls are
        at least :data:`_REQUEST_INTERVAL_SECONDS` apart.

        The bookkeeping is best-effort: read-then-write inside a
        short advisory lock keeps two workers from each sleeping
        based on a stale "last call" stamp, but a crashed worker
        cannot leak anything because the lock is session-scoped and
        the timestamp is just a hint.
        """
        backend = self.backend_record
        if _REQUEST_INTERVAL_SECONDS <= 0:
            return
        param_model = self.env["ir.config_parameter"].sudo()
        key = f"connector_freee_base.last_call_at.{backend.id}"
        cr = self.env.cr
        try:
            cr.execute(
                "SELECT pg_try_advisory_lock(%s, %s)",
                (_RATE_LIMIT_LOCK_NS, backend.id),
            )
            got_lock = cr.fetchone()[0]
            if not got_lock:
                # Another worker is updating the timestamp right now;
                # skip the throttle this call rather than block. The
                # channel cap still serialises queue-job paths.
                return
            try:
                last_raw = param_model.get_param(key)
                now = datetime.utcnow()
                if last_raw:
                    try:
                        last = datetime.fromisoformat(last_raw)
                    except ValueError:
                        # Corrupt timestamp — overwrite below and skip
                        # the wait for this call rather than failing.
                        _logger.debug(
                            "freee throttle: ignoring unparseable last-call "
                            "stamp %r for backend %s",
                            last_raw,
                            backend.id,
                        )
                    else:
                        elapsed = (now - last).total_seconds()
                        wait = _REQUEST_INTERVAL_SECONDS - elapsed
                        if 0 < wait <= _RATE_LIMIT_MAX_SLEEP_SECONDS:
                            time.sleep(wait)
                param_model.set_param(key, datetime.utcnow().isoformat())
            finally:
                cr.execute(
                    "SELECT pg_advisory_unlock(%s, %s)",
                    (_RATE_LIMIT_LOCK_NS, backend.id),
                )
        except Exception:  # noqa: BLE001 — throttle must never break a call
            _logger.exception(
                "freee throttle bookkeeping failed for backend %s; "
                "proceeding without it",
                backend.id,
            )

    def _call(self, method, path, params=None, json_body=None):
        """Send ``method path`` with one transparent 401-retry.

        On a fresh 401 we force the token to be re-fetched (clearing
        ``token_expires_at`` so ``_get_access_token`` runs the locked
        refresh) and re-issue the request once. A second 401 surfaces
        as a non-retryable :class:`FreeeAPIError` so the operator
        knows manual re-authorization is needed.
        """
        backend = self.backend_record
        url = self._build_url(path)
        self._throttle()
        for attempt in (0, 1):
            headers = self._build_headers()
            timeout = backend.request_timeout or DEFAULT_REQUEST_TIMEOUT
            try:
                response = requests.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    json=json_body,
                    timeout=timeout,
                )
            except requests.exceptions.RequestException as err:
                # surface the network-layer cause on the worker
                # log so an operator can tell DNS failure from TLS
                # error from connect timeout without having to enable
                # the H1-leaking payload debug toggle.
                _logger.warning(
                    "freee %s %s network error after %ss: %s",
                    method,
                    path,
                    timeout,
                    err,
                )
                raise NetworkRetryableError(
                    f"freee {method} {path} failed: {err}"
                ) from err

            if response.status_code == 401 and attempt == 0:
                # token may have been rotated/revoked on freee
                # without us noticing (e.g. admin invalidated the app
                # via the freee console). Force a fresh ``refresh_token``
                # exchange and retry the call exactly once. If the
                # refresh itself fails, ``_refresh_access_token`` raises
                # and we never reach the second iteration.
                _logger.warning(
                    "freee %s %s returned 401; forcing token refresh and "
                    "retrying once",
                    method,
                    path,
                )
                backend.sudo().write({"token_expires_at": False})
                backend.sudo()._refresh_access_token()
                continue

            return self._handle_response(method, path, response)

    def _handle_response(self, method, path, response):
        status = response.status_code
        if 200 <= status < 300:
            if not response.content:
                return None
            try:
                return response.json()
            except ValueError as err:
                raise FreeeAPIError(
                    _("freee returned a non-JSON response " "(%(method)s %(path)s).")
                    % {"method": method, "path": path}
                ) from err

        body = self._safe_json(response)
        if status == 401:
            # Reached only on the second consecutive 401 (the auto-
            # retry in :meth:`_call` already consumed the first one).
            # Refresh did not help — the operator must re-authorize.
            _logger.warning(
                "freee %s %s still 401 after refresh; re-authorization needed",
                method,
                path,
            )
            raise FreeeAPIError(
                _(
                    "freee rejected the access token even after a refresh "
                    "(HTTP 401). Re-authorize the backend."
                )
            )
        if status == 429:
            # freee can answer 429 either for a short burst (a
            # sensible ``Retry-After`` of a few seconds) or for a
            # daily/hourly quota (header absent, or a multi-hour
            # value). Cap the back-off so a daily-limit answer does
            # not freeze the queue_job worker for the rest of the
            # day; queue_job will retry every hour and the nightly
            # cron will catch the long tail.
            retry_after_raw = response.headers.get("Retry-After")
            try:
                retry_after = int(retry_after_raw) if retry_after_raw else 600
            except (TypeError, ValueError):
                retry_after = 600
            if retry_after > RATE_LIMIT_MAX_BACKOFF_SECONDS:
                _logger.warning(
                    "freee %s %s 429 with Retry-After=%ss (likely daily "
                    "limit); capping retry to %ss",
                    method,
                    path,
                    retry_after,
                    RATE_LIMIT_MAX_BACKOFF_SECONDS,
                )
                retry_after = RATE_LIMIT_MAX_BACKOFF_SECONDS
            else:
                _logger.warning(
                    "freee %s %s 429 rate-limited; retrying in %ss",
                    method,
                    path,
                    retry_after,
                )
            raise RetryableJobError(
                f"freee rate-limited request {method} {path}",
                seconds=retry_after,
                ignore_retry=True,
            )
        if status in RETRYABLE_STATUS:
            _logger.warning(
                "freee %s %s returned retryable HTTP %s", method, path, status
            )
            raise RetryableJobError(
                f"freee {method} {path} returned HTTP {status}: {body}",
                seconds=30,
            )
        # Non-retryable 4xx: log a warning (without echoing payload —
        # ``body`` is freee's error structure, which is the diagnostic
        # the operator needs and does not carry the request body).
        _logger.warning("freee %s %s failed (HTTP %s): %s", method, path, status, body)
        raise FreeeAPIError(
            _("freee %(method)s %(path)s failed (HTTP %(status)s): %(body)s")
            % {"method": method, "path": path, "status": status, "body": body}
        )

    @staticmethod
    def _safe_json(response):
        try:
            return response.json()
        except ValueError:
            return response.text
