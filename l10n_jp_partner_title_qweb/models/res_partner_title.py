# Copyright 2018-2019 Quartile Limited
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


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

    @api.constrains('lang_id', 'for_company')
    def _check_lang_id_for_company(self):
        for record in self:
            if record.lang_id and self.search_count(
                    [('lang_id', '=', record.lang_id.id),
                     ('for_company', '=', record.for_company)]) > 1:
                raise ValidationError(_('You cannot have more than one record '
                                        'for a combination of "Language" and '
                                        '"For Company".'))
