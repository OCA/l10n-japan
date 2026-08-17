# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""freee record deleter abstract base.

Concrete deleters single-inherit ``freee.deleter`` so they only
declare ``_apply_on``.
"""

from odoo.addons.component.core import AbstractComponent


class FreeeDeleter(AbstractComponent):
    _name = "freee.deleter"
    _inherit = ["base.deleter", "base.freee.connector"]
    _usage = "record.deleter"
