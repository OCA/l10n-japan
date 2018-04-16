# -*- coding: utf-8 -*-
# Copyright 2018 Quartile Limited
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import jaconv

from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    name_roman = fields.Char(
        compute='_get_name_roman',
        store=True,
    )
    description_roman = fields.Char(
        compute='_get_description_roman',
        store=True,
    )
    description_sale_roman = fields.Char(
        compute='_get_description_sale_roman',
        store=True,
    )
    default_code_roman = fields.Char(
        compute='_get_default_code_roman',
        store=True,
    )

    @api.depends('name')
    def _get_name_roman(self):
        for pt in self:
            if pt.name:
                pt.name_roman = self.get_roman_string(pt.name)

    @api.depends('description')
    def _get_description_roman(self):
        for pt in self:
            if pt.description:
                pt.description_roman = self.get_roman_string(
                    pt.description)

    @api.depends('description_sale')
    def _get_description_sale_roman(self):
        for pt in self:
            if pt.description_sale:
                pt.description_sale_roman = self.get_roman_string(
                    pt.description_sale)

    @api.depends('default_code')
    def _get_default_code_roman(self):
        for pt in self:
            if pt.default_code:
                pt.default_code_roman = self.get_roman_string(
                    pt.default_code)

    def get_roman_string(self, string):
        from pykakasi import kakasi
        kakasi = kakasi()
        kakasi.setMode('H', 'a')
        kakasi.setMode('K', 'a')
        kakasi.setMode('J', 'a')
        kakasi.setMode('r', 'Hepburn')
        kakasi.setMode('s', True)
        roman_converter = kakasi.getConverter()
        return jaconv.z2h(roman_converter.do(string))
