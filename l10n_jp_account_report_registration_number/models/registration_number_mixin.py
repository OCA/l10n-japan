# Copyright 2023 Quartile Limited
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class RegistrationNumberMixin(models.AbstractModel):
    _name = "registration.number.mixin"
    _description = "Registraction Number Mixin"

    def _show_registration_number(self):
        """This method is expected to be extended by the concrete models as necessary."""
        self.ensure_one()
        if self.company_id.account_fiscal_country_id.code != "JP":
            return False
        if self.partner_id.country_id.code != "JP":
            return False
        return True
