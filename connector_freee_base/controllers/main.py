# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import html
import logging

from odoo import _, http
from odoo.exceptions import ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)


class FreeeOAuthController(http.Controller):
    """Handles the OAuth 2.0 redirect from freee.

    freee redirects the authorized user to this URL with ``code`` and
    ``state`` query parameters. We resolve the backend record from the
    state, exchange the code for tokens and redirect the user back to
    the backend form.
    """

    # ``csrf=False`` is safe here because CSRF protection is provided by
    # the OAuth 2.0 ``state`` parameter (RFC 6749 §10.12): the controller
    # only accepts ``state`` values it itself minted on
    # ``freee.backend.action_authorize`` and verifies them in
    # ``freee.backend._resolve_callback``. Odoo's default CSRF token
    # cannot apply because freee — not Odoo — initiates this redirect.
    @http.route(
        "/freee/oauth/callback",
        type="http",
        auth="user",
        methods=["GET"],
        csrf=False,
        save_session=False,
    )
    def callback(self, code=None, state=None, error=None, **kwargs):
        # Defence in depth: even though the secret state nonce is
        # unguessable, only freee admins should ever land here. The
        # `auth="user"` decorator only verifies *some* user is logged
        # in; this group check ensures it is one entitled to manage
        # freee credentials.
        if not request.env.user.has_group("connector_freee_base.group_freee_admin"):
            return self._render_error(
                _("Only freee administrators may complete authorization.")
            )
        if error:
            _logger.warning("freee OAuth returned error: %s", error)
            return self._render_error(_("freee authorization was denied: %s") % error)
        if not code or not state:
            return self._render_error(_("Missing OAuth parameters."))
        try:
            backend = request.env["freee.backend"].sudo()._resolve_callback(code, state)
        except ValidationError as err:
            return self._render_error(str(err))

        action = request.env.ref(
            "connector_freee_base.action_freee_backend",
            raise_if_not_found=False,
        )
        if action:
            return request.redirect(f"/odoo/action-{action.id}/{backend.id}")
        return request.redirect(f"/odoo/freee.backend/{backend.id}")

    @staticmethod
    def _render_error(message):
        safe = html.escape(str(message))
        return request.make_response(
            f"<h2>freee OAuth Error</h2><pre>{safe}</pre>",
            headers=[("Content-Type", "text/html; charset=utf-8")],
            status=400,
        )
