##############################################################################
#
#    eOrder - Sales Order
#    Module: Main Module
#    Copyright (C) 2018 onwards Joven Lawrence Gersaniba.
#    All Rights Reserved
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

#import time
#from dateutil.relativedelta import relativedelta
#from datetime import datetime, timedelta
from odoo import api, fields, models, tools, _
from odoo.exceptions import Warning, UserError, ValidationError
#import openerp.addons.decimal_precision as dp

#class custom_hr(models.Model):

#    _inherit = "hr.employee"

#    #Custom Field Definitions
#    physician = fields.Boolean(string='Physician')
#    specialization = fields.Many2one('hr.physician.specialization',string='Specialization')

class custom_hr_department(models.Model):

    _inherit = "hr.department"

    #Custom Field Definitions
    stock_location_id = fields.Many2one('stock.location', string='Default Stock Location', domain=[('usage', '=', 'internal')])
