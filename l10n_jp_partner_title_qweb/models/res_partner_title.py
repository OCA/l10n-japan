# -*- coding: utf-8 -*-
# Copyright 2018 Quartile Limited
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import models, fields


class ResPartnerTitle(models.Model):
    _inherit = 'res.partner.title'

    display_position = fields.Selection(
        [('before', "Before Name"), ('after', "After Name")],
        string='Display Position',
    )
    lang_id = fields.Many2one(
        'res.lang',
        string='Language',
        help='The Language for which this title should be proposed in partner '
             'records.',
    )
    for_company = fields.Boolean(
        'For Company',
        help='If selected, this title should be proposed to company partners '
             'according to the language selection of the partner.',
    )
