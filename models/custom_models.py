# -*- coding: utf-8 -*-

from odoo import models, fields, api, tools, _
from odoo.exceptions import Warning, UserError, ValidationError

#Religion
class ejob_religion(models.Model):
    _name = "ejob.religion"
    name = fields.Char(string='Religion', size=80)

#Nationality
class ejob_nationality(models.Model):
    _name = "ejob.nationality"
    name = fields.Char(string='Nationality', size=80)

#Barangays
class ejob_barangay(models.Model):
    _name = "ejob.barangays"
    name = fields.Char(string='Barangay', required=True, size=80)
    city_id = fields.Many2one('ejob.cities', string='City', required=True, ondelete='restrict')

#City
class ejob_city(models.Model):
    _name = "ejob.cities"
    name = fields.Char(string='City', required=True, size=80)

#Zip Code Reference
class ejob_zip_ref(models.Model):
    _name = "ejob.zip.ref"
    name = fields.Char(string='Zip Code', size=10, required=True)
    city_id = fields.Many2one('ejob.cities', string='City', required=True, ondelete='restrict')
    state_id = fields.Many2one("res.country.state", string='State', required=True, ondelete='restrict')
    country_id = fields.Many2one('res.country', string='Country', required=True, ondelete='restrict')

    @api.multi
    def name_get(self):
        res = []
        for rec in self:
            name = rec.name + ' ' or ''
            if rec.city_id:
                name += rec.city_id.name +', '
            if rec.state_id:
                name += rec.state_id.name +', '
            if rec.country_id:
                name += rec.country_id.name
            res.append((rec.id, name))
        return res

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search(['|','|',('city_id', 'ilike', name),('state_id', 'ilike', name),('country_id', 'ilike', name)] + args, limit=limit)
        if not recs:
            recs = self.search([('name', operator, name)] + args, limit=limit)
        return recs.name_get()
