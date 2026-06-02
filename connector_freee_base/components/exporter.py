# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""freee record exporter abstract base.

Concrete record exporters single-inherit ``freee.exporter`` so they
only declare ``_apply_on``. Matches the OCA pattern (e.g.
``prestashop.exporter``).
"""

from odoo.addons.component.core import AbstractComponent


class FreeeExporter(AbstractComponent):
    _name = "freee.exporter"
    _inherit = ["base.exporter", "base.freee.connector"]
    _usage = "record.exporter"
