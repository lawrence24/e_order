# -*- coding : utf-8 -*-

from odoo import fields, models, api, tools, _

#Cashier Management
class ejob_cashier(models.Model):

    _name = 'ejob.cashier'
    _description = 'Customer SOA'
    _order = "id desc"

    @api.depends('orders')
    def _compute_charges(self):
        if not self.ids:
            #Update calculated fields
            self.update({
                'total_items_count': 0,
                'total_services_fee': 0.0,
                'total_discount': 0.0,
            })
            return True

        for payment in self:
            total_items_count = 0
            total_services_fee = 0.0
            total_discount = 0.0
            #raise UserError('Debug: %s' % (list(table.pos_order_ids)))
            if payment.orders:
                for order in payment.orders:
                    for orderline in order.services:
                        #if chargeline.state == 'Done':
                        total_items_count += 1
                        total_services_fee += orderline.sub_total
                        total_discount += orderline.discount_amount

            payment.update({
                'total_items_count': total_items_count,
                'total_services_fee': total_services_fee,
                'total_discount': total_discount,
            })

    @api.depends('total_services_fee','total_paid')
    def _compute_balance(self):
        for payment in self:
            if payment.payment_type == 'Down Payment':
                payment.balance = 0
            elif payment.payment_type == 'A/R Payment':
                payment.balance = 0
            else:
                payment.balance = payment.total_services_fee - payment.total_paid

    @api.model
    def _default_currency(self):
        return self.env.user.company_id.currency_id or None

    @api.model
    def _get_pricelist(self):
        return self.partner_id.property_product_pricelist # and table.partner_id.property_product_pricelist.id or None

    name = fields.Char('Payment Ref#')
    partner_id = fields.Many2one('res.partner',string='Customer')
    payment_date = fields.Date('Payment Date', default=fields.Date.today())
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist', default=_get_pricelist)
    currency_id = fields.Many2one('res.currency', string='Currency', default= _default_currency)
    total_items_count = fields.Integer(compute='_compute_charges',string="Number of Charged Items")

    orders = fields.One2many('e.job.orders','payment_id',string='Orders')
    payments = fields.One2many('account.payment','payment_id',string='Payments')
    invoices = fields.One2many('account.invoice', 'payment_id', string='Customer Invoices')


    total_services_fee = fields.Float(compute='_compute_charges', string='Total Services')
    total_discount = fields.Float(compute='_compute_charges', string='Total Discount')
    total_paid = fields.Float(compute='_compute_amt_paid', string='Total Paid', digits=(12,2))
    total_down_payments = fields.Float('Total Payments', default=0.0)
    balance = fields.Float(compute='_compute_balance', string='Balance')
    payment_type = fields.Selection([
        ('Cash','Cash'),
        ('Charge Slip','Charge Slip'),
        ('Down Payment','Down Payment'),
        ('A/R Payment','A/R Payment')],'Payment Type', readonly=True, default='Cash')
    payment_due = fields.Date('Payment Due')

    user_id = fields.Many2one('res.users', string='Cashier', required=True, readonly=True, default=lambda self: self.env.uid)
    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=True, default=lambda self: self.env.user.company_id)
    state = fields.Selection([
        ('new','New'),
        ('inv','Invoiced'),
        ('partial','Partial-Paid'),
        ('paid','Paid')], 'Status', default='new')


    @api.depends('payments')
    def _compute_amt_paid(self):
        if not self.ids:
            #Update calculated fields
            self.update({
                'total_paid': 0.0,
            })
            return True

        for payment in self:
            total_paid = 0.0
            #raise UserError('Debug: %s' % (list(table.pos_order_ids)))
            if payment.payments:
                for pay in payment.payments:
                    total_paid += pay.amount

            #Update calculated fields
            payment.update({
                'total_paid': total_paid,
            })

    @api.depends('orders')
    def _compute_total_services(self):
        for rec in self:
            service_total = 0.0
            for line in rec.charge_line_ids:
                charge_total += line.net
            rec.charge_total = rec.currency_id.round(charge_total)



    @api.multi
    def create_invoice(self):
        payment_id = self.id
        payment_name = 'ORD ID: ' + self.name
        invoice_name = self.env['ir.sequence'].next_by_code('ejob.invoice.id')

        customer = self.partner_id.id
        customer_name = self.partner_id.name
        ar_account_id = self.partner_id.property_account_receivable_id and self.partner_id.property_account_receivable_id.id or False
        if not ar_account_id:
            raise UserError('Customer A/R account error! Please check the default receivable account of the customer.')
        fiscal_position_id = self.partner_id.property_account_position_id and self.partner_id.property_account_position_id.id or False

        invoice_obj = self.env['account.invoice']
        journal_obj = self.env['account.journal']
        ctr = 0
        success = False
        for orders in self.orders:
            invoice_lines = []
            invoice_discs = {}

            #Change to appropriate journal
            #journal = journal_obj.search([('charge_type','=',charges.charge_type)])
            #if journal:
            #    journal_id = journal[0].id
            #else:
            #    raise UserError('The Charge %s (%s) does not have a journal specified' % (charges.name,charges.charge_type))
            journal_id = 1

            #Process item invoices
            for order_line in orders.services:
                #if charge_line.state == 'draft':
                if order_line.product_id:
                    account_id = order_line.product_id.property_account_income_id.id or order_line.product_id.categ_id.property_account_income_categ_id.id
                    if not account_id:
                        raise UserError(
                                _('There is no income account defined for this product: "%s". You may have to install a chart of account from Accounting app, settings menu.') % \
                                    order_line.product_id.name)

                    unit_price = order_line.price_unit #- order_line.discount_amount
                    tax_ids = [(6, 0, [x.id for x in order_line.product_id.taxes_id])]
                    invoice_line = {
                        'name': order_line.name,
                        'origin': payment_name + ' [' + order_line.name + ']',
                        'account_id': account_id,
                        'price_unit': unit_price,
                        'quantity': order_line.qty,
                        'discount': order_line.discount_percentage,
                        'uom_id': order_line.product_id.uom_id.id,
                        'product_id': order_line.product_id.id,
                        'invoice_line_tax_ids': tax_ids,
                        'account_analytic_id': False,
                    }
                    invoice_lines.append(invoice_line)

            #Generate Invoice
            if len(invoice_lines) > 0:
                invoice = {
                    'date_invoice': self.payment_date, #fields.Datetime.now(),
                    'name': invoice_name,
                    'origin': payment_name,
                    'type': 'out_invoice',
                    'reference': invoice_name + '-' + payment_name,
                    'account_id': ar_account_id,
                    'partner_id': customer,
                    'currency_id': self.currency_id.id,
                    'journal_id': journal_id,
                    'payment_term_id': False,
                    'fiscal_position_id': fiscal_position_id,
                    'comment': 'Charges for: ' + customer_name,
                    'company_id': self.env.user.company_id.id,
                    'user_id': self.env.user.id,
                    'payment_id': payment_id,
                }

                inv_lines = []
                #Generate Invoice Lines
                for invline in invoice_lines:
                    inv_lines.append((0, 0, invline))
                invoice.update({'invoice_line_ids': inv_lines})

                #Create the Invoice
                invoice = invoice_obj.create(invoice)
                invoice.compute_taxes()
                success = True

                #Update the Charge status to Invoiced
                #charges.update({'state':'done'})
        if success:
            self.env.user.notify_info('Invoice created.',title='Invoice Generation', sticky=False)
            self.update({'state':'inv'})

    @api.multi
    def cancel_invoice(self):
        for rec in self:
            if rec.invoices:
                for invoice in rec.invoices:
                    invoice.unlink()
                rec.update({'state':'new'})
                #Reset all Charges to draft
                #for order in rec.orders:
                #    order.update({'state':'draft'})
                self.env.user.notify_info('All generated invoices are cancelled.',title='Invoice Cancellation', sticky=False)
            else:
                raise UserError('Error! There are no invoices generated for these charges.')


class custom_account_invoice(models.Model):
    _inherit = "account.invoice"

    payment_id = fields.Many2one('e.job.orders', string="Payment Record")
    date_invoice = fields.Date(string='Invoice Date',
        readonly=True, states={'draft': [('readonly', False)],'open': [('readonly', False)]}, index=True,
        help="Keep empty to use the current date", copy=False)

class custom_account_payment(models.Model):
    _inherit = "account.payment"

    payment_id = fields.Many2one('e.job.orders', string="Payment Record")
    invoice_ref = fields.Char (string='Invoice Reference')
    #tax_amt = fields.Float(string='Tax Amount', readonly=True, digits=(10,2))
    #vatable_amt = fields.Float(string='VATable Sales', readonly=True, digits=(10,2))
    #chk_payment_date = fields.Date (string='Check Date')
    #chk_payment_bank = fields.Many2one('estl.ref.banks',string='Bank')
    #chk_payment_branch = fields.Many2one('estl.ref.bank.branches',string='Branch')
    #chk_payment_checkno = fields.Char(string='Check/Card No.',size=30)

    #curr_bal = fields.Monetary(string='Current Balance', readonly=True)
    #balance = fields.Monetary(string='Balance', store=False, readonly=True, compute='_compute_balance')
