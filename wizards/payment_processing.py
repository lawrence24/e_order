# -*- coding : utf-8 -*-

import time

import odoo.addons.decimal_precision as dp

from odoo import models, fields, api, tools, _
from odoo.exceptions import Warning, UserError, ValidationError

class PaymentProcessing(models.TransientModel):
    _name = "ejob.payment.wiz"
    _description = "Payment Processing Wizard"

    @api.multi
    @api.model
    def _default_currency_id(self):
        payment_obj = self.env['ejob.cashier']
        payment = payment_obj.browse(self._context.get('active_ids'))[0]
        currency = payment.currency_id or False
        if not currency:
            currency = self.env.user.company_id and self.env.user.company_id.id or False
            if not currency:
                return False
        return currency

    @api.model
    def _default_journal_id(self):
        jrnl_obj = self.env['account.journal']
        jrnl = jrnl_obj.search([('type', '=', 'cash')])[0]
        return jrnl

    @api.model
    def _default_total_services_fee(self):
        if self._context.get('active_ids'):
            payment_obj =  self.env['ejob.cashier']
            payment = payment_obj.browse(self._context.get('active_ids'))[0]
            return payment.total_services_fee
        else:
            return 0

    @api.model
    def _default_balance(self):
        if self._context.get('active_ids'):
            payment_obj = self.env['ejob.cashier']
            payment = payment_obj.browse(self._context.get('active_ids'))[0]
            return payment.balance
        else:
            return 0

    @api.model
    def _default_amt_paid(self):
        if self._context.get('active_ids'):
            payment_obj = self.env['ejob.cashier']
            payment = payment_obj.browse(self._context.get('active_ids'))[0]
            return payment.balance
        else:
            return 0

    payment_date = fields.Date('Payment Date', default=fields.Date.today())
    journal_id = fields.Many2one('account.journal', string="Journal",domain=[('type','in',('cash','bank'))] , default=_default_journal_id)
    journal_type = fields.Selection([
        ('sale','Sale'),
        ('purchase','Purchase'),
        ('cash','Cash'),
        ('bank','bank'),
        ('general','Miscellaneous'),
    ], string="Journal Type")
    currency_id = fields.Many2one('res.currency', string="Currency",track_visibility='always',
        default=_default_currency_id)
    total_services_fee = fields.Float(string='Total Charges', default=_default_total_services_fee, digits=(12,2))
    balance = fields.Float(string='Balance', default=_default_balance, degits=(12,2))
    amt_paid = fields.Float(string='Amount Paid', default=_default_amt_paid, digits=(12,2))
    amt_tendered = fields.Float(string='Amount Tendered', digits=(12,2))
    change = fields.Float(string='Change', compute='_compute_change', digits=(12,2))
    communication = fields.Char(string='Note')

    @api.multi
    @api.onchange('amt_tendered')
    def _onchange_amt_tendered(self):
        if self.amt_tendered > 0:
            self.change = self.amt_tendered - self.amt_paid
        else:
            self.change = 0
    @api.multi
    @api.onchange('amt_paid')
    def _onchange_amt_paid(self):
        if self.amt_tendered > 0:
            self.change = self.amt_tendered - self.amt_paid
        else:
            self.change = 0

    @api.onchange('journal_id')
    def _onchange_journal_id(self):
        if self.journal_id:
            self.journal_type = self.journal_id.type
        else:
            self.journa_type = ''


    @api.one
    @api.depends('amt_tendered','amt_paid')
    def _compute_change(self):
        if self.amt_tendered > 0:
            change = self.amt_tendered - self.amt_paid
        else:
            change = 0
        return change

    def _get_invoices(self,payment):
        payment_obj = self.env['ejob.cashier']
        #payment = payment_obj.browse(self._context.get('active_ids'))[0]
        if payment:
            inv_obj = self.env['account.invoice']
            #invoices = inv_obj.search([('payment_id','=',payment.id)])
            inv_ids = []
            for invoice in payment.invoices:
                #Check draft invoices and validate automatically
                #for invoice in invoices:
                if invoice.state == 'draft':
                    #invoice.signal_workflow('invoice_open')
                    invoice.action_invoice_open()
                    inv_ids.append(invoice.id)
                    #raise UserError('Debug! Values: %s [%s]' % (invoice.name,invoice.state))

            #self.env.cr.commit()

            amt_paid = self.amt_paid
            for invoice in payment.invoices:
                if invoice.state == 'open':
                    if amt_paid > 0.0 and invoice.residual > 0.0:
                        if invoice.id not in inv_ids:
                            inv_ids.append(invoice.id)
                    else:
                        break
                    amt_paid -= invoice.residual
            if len(inv_ids) <= 0:
                raise UserError('No invoice can be processed for payment. Please check if the invoices are cancelled or already paid.')
            else:
                self.env.user.notify_info('Draft invoices are validated and added to the payment transaction.',title='Invoice Validation', sticky=False)
            return inv_obj.browse(inv_ids)
        else:
            raise UserError('System Error! Cannot retrieve payment record.')


    @api.multi
    def create_voucher(self):
        if round(self.amt_paid,2) > 0:
            payment_obj = self.env['ejob.cashier']
            payment_id = self._context.get('active_ids')
            payment = payment_obj.browse(payment_id)[0]
            bal = round(payment.balance,2)
            if self.amt_paid <= bal:
                paymethod_obj = self.env['account.payment.method']
                payment_type = 'inbound'
                payment_method = paymethod_obj.search([('payment_type', '=', payment_type)])
                if payment_method:
                    payment_method_id = payment_method[0]
                else:
                    raise UserError("No payment method defined.")

                #if payment.name == 'NEW':
                    #Generate OR#
                    #payment_ref = self.env['ir.sequence'].next_by_code('eSTL.payment.ref.no')
                #else:
                    #payment_ref = payment.name

                if round(self.amt_paid,2) == bal:
                    payment_state = 'paid'

                else:
                    payment_state = 'partial'


                payment_data = {
                    'journal_id': self.journal_id.id,
                    'payment_method_id': payment_method_id.id,
                    'payment_date': self.payment_date,
                    'communication': self.communication,
                    'invoice_ids': [(4, inv.id, None) for inv in self._get_invoices(payment)],
                    'payment_type': payment_type,
                    'amount': self.amt_paid,
                    'currency_id': self.currency_id.id,
                    'partner_id': payment.partner_id.id,
                    'partner_type': 'customer',
                    'payment_id': payment.id,
                    'invoice_ref': payment.name,
                    #'tax_amt': self.vat,
                    #'vatable_amt': self.vatable,
                    #'curr_bal': self.curr_bal,
                }
                #if self.journal_id.type == 'bank':
                    #payment_data.update({
                        #'chk_payment_date': self.chk_payment_date,
                        #'chk_payment_bank': self.chk_payment_bank and self.chk_payment_bank.id or None,
                        #'chk_payment_branch': self.chk_payment_branch and self.chk_payment_branch.id or None,
                        #'chk_payment_checkno': self.chk_payment_checkno,
                    #})
                payrec = self.env['account.payment'].create(payment_data)
                #payrec.post()
                #raise UserError("Debug!")

                #Set the Charges state to 'Paid'
                for order in payment.orders:
                    order.write({'state': 'paid'})
                #Update the Payment Record
                payment_val = {'state':payment_state}
                payment.update(payment_val)
                self.env.user.notify_info('Payment transactions are posted and customer account was updated.',title='Payment Posting', sticky=False)
            else:
                raise UserError("The amount paid must be less than or equal to the current balance (%s)." % payment.balance)
        else:
            raise UserError("Please specify the amount paid.")
        #CLose the wizard
        return {'type': 'ir.actions.act_window_close'}
