# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.addons.component.core import AbstractComponent


class BaseFreeeConnectorComponent(AbstractComponent):
    """Base component for all freee connector components.

    Sets the collection (``_collection``) to ``freee.backend`` so concrete
    components automatically resolve against the freee backend record.
    """

    _name = "base.freee.connector"
    _inherit = "base.connector"
    _collection = "freee.backend"
