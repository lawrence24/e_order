# -*- coding : utf-8 -*-

import time

import odoo.addons.decimal_precision as dp

#from odoo.modules import get_module_resource
from odoo import api, fields, models, tools, _
from odoo.exceptions import Warning, UserError, ValidationError

class OrderSlipEntryWizard(models.TransientModel):
    _name = "ejob.order.slip.entry.wiz"
    _description = "Customer Order Slip Entry Wizard"

    @api.model
    def _get_default_partner_id(self):
        if self._context.get('active_ids'):
            payment_id = self._context.get('active_ids')[0]
            payment_obj = self.env['ejob.cashier']
            return payment_obj.browse(payment_id).partner_id.id
        return False

    partner_id = fields.Many2one("res.partner", string="Customer", default=_get_default_partner_id, readonly=True)
    order_id = fields.Many2one('e.job.orders', string='Charge Slip', domain=[('state', '=', 'bill')], required=True)
    total_services_fee = fields.Float(digits=(12,2), string='Total', related='order_id.total_services_fee', store=False, readonly=True)

    #Form Button Actions
    @api.multi
    def add_order_slip(self):
        for rec in self:
            if rec.order_id and self._context.get('active_ids'):
                payment_id = self._context.get('active_ids')[0]
                rec.order_id.payment_id = payment_id
