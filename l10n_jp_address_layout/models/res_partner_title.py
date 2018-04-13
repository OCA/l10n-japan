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
