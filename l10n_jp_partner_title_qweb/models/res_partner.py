# Copyright 2018-2019 Quartile Limited
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # we make title a computed field instead of using onchange to update it
    # because onchange is not triggered when a user signs up from portal
    title = fields.Many2one(
        compute='_compute_title',
        store=True,
        readonly=False,
    )

    @api.multi
    @api.depends('lang', 'is_company')
    def _compute_title(self):
        for partner in self:
            # handle the case NewId is returned for partner.id (i.e. onchange)
            partner_id = self._origin.id if isinstance(
                partner.id, models.NewId) else partner.id
            # no title proposal for partners linked to internal users and
            # companies (res.company)
            if not partner.lang or partner.user_ids and \
                    not partner.user_ids.share or \
                    self.env['res.company'].search(
                        [('partner_id', '=', partner_id)]):
                partner.title = False
            else:
                lang_id = self.env['res.lang'].search(
                    [('code', '=', partner.lang)], limit=1).id
                title = self.env['res.partner.title'].search(
                    [('lang_id', '=', lang_id),
                     ('for_company', '=', partner.is_company)], limit=1)
                partner.title = title.id if title else False
