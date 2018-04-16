# -*- coding: utf-8 -*-
# Copyright 2018 Quartile Limited
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale


class WebsiteSaleExtended(WebsiteSale):

    def _get_search_domain(self, search, category, attrib_values):
        domain = super(WebsiteSaleExtended, self).\
            _get_search_domain(search, category, attrib_values)
        if search:
            for srch in search.split(" "):
                search_roman = request.env[
                    'product.template'].get_roman_string(srch)
                if search_roman != srch:
                    i = 0
                    for condition in domain:
                        if srch in condition:
                            domain[i] = ('%s_roman' % condition[0],
                                         condition[1], search_roman)
                        i = i + 1
        return domain
