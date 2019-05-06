# Copyright 2019 Quartile Limited
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import jaconv
import json
import urllib

from odoo import models, fields, api, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    country_id = fields.Many2one(
        default=lambda self: self.env.ref('base.jp')
    )

    @api.onchange('zip')
    def _onchange_zip(self):
        if self.zip:
            self.zip, msg = self.check_zip(self.zip)
            if not self.zip:
                return msg
            request_url = 'http://zipcloud.ibsnet.co.jp/api/search?zipcode' \
                          '=%s' % self.zip
            request = urllib.request.Request(request_url)
            response_data = json.loads(
                urllib.request.urlopen(request).read().decode('utf-8'))
            self.state_id = False
            self.city = False
            self.street = False
            self.street2 = False
            if response_data['status'] != 200:
                self.zip = False
                return {
                    'warning': {
                        'title': _("Error"),
                        'message': response_data['message']
                    }
                }
            else:
                address_data = response_data['results']
                if address_data:
                    self.state_id = self.env['res.country.state'].search([
                        ('name', '=', address_data[0]['address1'])
                    ], limit=1)
                    self.city = address_data[0]['address2']
                    self.street = address_data[0]['address3']

    def check_zip(self, zip):
        msg = {}
        field = jaconv.z2h(zip, ascii=True, digit=True).replace("-", "")
        if not field.isdigit():
            field = False
            msg = {
                'warning': {
                    'title': _("Error"),
                    'message': _("Only digits are allowed.")
                }
            }
        if len(field) != 7:
            field = False
            msg = {
                'warning': {
                    'title': _("Error"),
                    'message': _("Post code should be 7 digits.")
                }
            }
        return field, msg
