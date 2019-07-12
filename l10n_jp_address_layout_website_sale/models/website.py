# Copyright 2019 Quartile Limited
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo.http import request
from odoo import models


class Website(models.Model):
    _inherit = 'website'

    def get_partner_country_info(self):
        if request.env.user.partner_id.country_id:
            return str(request.env.user.partner_id.country_id.id)
        return False

    def display_japan_address_layout(self):
        return request.env.user.partner_id.country_id and \
            request.env.user.partner_id.country_id.code == 'JP' and \
                request.env.user.lang and request.env.user.lang == 'ja_JP'
