# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""freee binder abstract base.

Concrete binders (one per binding model) single-inherit ``freee.binder``
so they only have to declare ``_apply_on``. The freee binding field
names (``external_id`` / ``backend_id`` / ``odoo_id`` / ``sync_date``)
are centralised here.
"""

from odoo.addons.component.core import AbstractComponent


class FreeeBinder(AbstractComponent):
    _name = "freee.binder"
    _inherit = ["base.binder", "base.freee.connector"]

    _external_field = "external_id"
    _backend_field = "backend_id"
    _odoo_field = "odoo_id"
    _sync_date_field = "sync_date"
