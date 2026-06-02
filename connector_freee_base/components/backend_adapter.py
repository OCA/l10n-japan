# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""Concrete adapter bound to ``freee.backend``.

Picker wizards (account items, partners, sections, items, tax codes,
walletables) and the backend model's own company-fetch helpers run
inside ``backend.work_on("freee.backend")`` and ask for the
``backend.adapter`` usage to make general-purpose freee API calls
(``/api/1/companies``, ``/api/1/account_items``, etc.). This adapter
binds ``freee.adapter``'s HTTP verbs to the ``freee.backend`` model
so those resolutions succeed without needing a model-specific adapter
subclass per wizard.
"""

from odoo.addons.component.core import Component


class FreeeBackendAdapter(Component):
    _name = "freee.backend.adapter"
    _inherit = "freee.adapter"
    _apply_on = "freee.backend"
