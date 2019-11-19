# -*- coding : utf-8 -*-

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from odoo import fields, models, api, tools, _
from odoo.exceptions import Warning, UserError, ValidationError

class custom_partner(models.Model):
    _inherit = "res.partner"

    @api.multi
    def _draft_invoice_total(self):
        account_invoice_report = self.env['account.invoice.report']
        if not self.ids:
            self.total_draft_invoices = 0.0
            return True

    @api.depends('his_birthdate')
    def _calc_age(self):
        for line in self:
            line.age = self.compute_age_from_dates(line.his_birthdate)

    def compute_age_from_dates(self, customer_dob):
        now=datetime.strptime(fields.Datetime.now()[:10], '%Y-%m-%d')
        if (customer_dob):
            dob=datetime.strptime(customer_dob, '%Y-%m-%d')
            delta =relativedelta (now, dob)
            years_months_days = str(delta.year) + "y " + str(delta.month) + "m " + str(delta.day) + "d"
        else:
            years_months_days = "No Birthdate"
        return years_months_days

    #Custom Fields Definitions
    last_name = fields.Char(string='Last Name')
    first_name = fields.Char(string='First Name')
    middle_name = fields.Char(string='Middle Name')
    is_customer = fields.Boolean(string='Customer')
    gender = fields.Selection([('MALE','male'),('FEMALE','female')], string="Gender")
    civil_status = fields.Selection([('SINGLE','single'),('MARRIED','married'),('SEPARATED','separated'),('DIVORCED','divorced'),('WIDOW','widowed')],string="Civil Status")
    his_birthdate = fields.Date('Birthdate')
    age = fields.Char(compute='_calc_age', string='Age', size=50, readonly=True)
    age_yrs = fields.Integer('Age (Years)')
    nationality = fields.Many2one('ejob.nationality',string='Nationality')
    religion = fields.Many2one('ejob.religion', string='Religion')

    barangay = fields.Many2one('ejob.barangays',string='Barangay')
    city_id = fields.Many2one('ejob.cities',string='City')
    zip_id = fields.Many2one('ejob.zip.ref',string='Zip')

    #credit_plus_draft_inv = fields.Float(compute='_compute_credit_plus_draft_inv', string="Total Credit with Draft Invoices", digits=(12,2))
    #total_draft_invoices = fields.Float(compute='_draft_invoice_total', string="Total Draft Invoices", digits=(14,2))

    total_draft_charges = fields.Float(compute='_draft_charges_total', string="Total Draft Charges", digits=(14,2))
    total_charges_bal = fields.Float(compute='_draft_charges_bal_total', string="Current Balance", digits=(14,2))
    date_last_visit = fields.Datetime('Last Visit',default=lambda self: fields.datetime.now())

    @api.onchange('ref','last_name','first_name','middle_name')
    def customer_name_change(self):
        vals = {}
        if self.customer:
            name = ''
            if self.ref:
                name += '[' + self.ref + '] '
            if self.last_name:
                name += self.last_name + ', '
            if self.first_name:
                name += self.first_name + ' '
            if self.middle_name:
                name += self.middle_name

            vals.update({'name': name.upper()})
        self.update(vals)

    @api.onchange('barangay')
    def customer_barangay_change(self):
        if self.barangay:
            if self.barangay.city_id:
                vals = {'city_id':self.barangay.city_id.id}
                self.update(vals)

    @api.onchange('city_id')
    def customer_city_id_change(self):
        if self.city_id:
            vals = {'city':self.city_id.name}
            self.update(vals)

    @api.onchange('zip_id')
    def customer_zip_id_change(self):
        if self.zip_id:
            vals = {'zip':self.zip_id.name}
            if self.zip_id.city_id:
                vals.update({'city_id':self.zip_id.city_id.id})
            if self.zip_id.state_id:
                vals.update({'state_id':self.zip_id.state_id.id})
            if self.zip_id.country_id:
                vals.update({'country_id':self.zip_id.country_id.id})
            self.update(vals)

    @api.multi
    def gen_id_number(self):
        for rec in self:
            if not rec.ref or rec.ref == '':
                ref = self.env['ir.sequence'].next_by_code('ejob.id.number')
                name = '[' + ref + '] '
                if rec.last_name:
                    name += rec.last_name + ', '
                if rec.first_name:
                    name += rec.first_name + ' '
                if rec.middle_name:
                    name += rec.middle_name
                rec.update({'ref':ref, 'name': name.upper()})

    @api.one
    def _compute_credit_plus_draft_inv(self):
        self.credit_plus_draft_inv = self.credit + self.total_draft_invoices

    @api.multi
    def _draft_charges_total(self):
        if not self.ids:
            self.total_draft_pos_orders = 0.0
            return True

        charges_obj = self.env['e.job.orders']

        #user_currency_id = self.env.user.company_id.currency_id.id
        for partner in self:
            total = 0
            charges = charges_obj.search([('partner_id', '=', partner.id), ('state', '=', 'bill'), ('company_id', '=', self.env.user.company_id.id)])
            for charge in charges:
                total += charge.total_services_fee

            partner.total_draft_charges = total

    @api.multi
    def _draft_charges_bal_total(self):
        if not self.ids:
            self.total_charges_bal = 0.0
            return True

        payments_obj = self.env['ejob.cashier']

        #user_currency_id = self.env.user.company_id.currency_id.id
        for partner in self:
            total = 0
            charges = payments_obj.search([('partner_id', '=', partner.id), ('state', 'in', ('inv','partial')), ('company_id', '=', self.env.user.company_id.id)])
            for charge in charges:
                total += charge.balance

            partner.total_charges_bal = total

    @api.multi
    def manage_charges(self):
        for rec in self:
            partner_id = rec.id
            pricelist = rec.property_product_pricelist
            currency = self.env.user.company_id and self.env.user.company_id.currency_id or False
            #Check if the customer have a current (NEW) Charge
            charge_obj=self.env['e.job.orders']
            new_charges = charge_obj.search([('partner_id','=',partner_id),('state','in',('new','submit'))])
            if new_charges:
                #A NEW Charge Record is already created, get charge_id
                current_charge_id = new_charges[0].id


            else:

                #No NEW charge, create a new Charge Record
                srv_ref = self.env['ir.sequence'].next_by_code('e.job.orders')
                #srv_line_ref = self.env['ir.sequence'].next_by_code('eHC.charge.line.number')
                charge = charge_obj.create({'name': srv_ref, 'partner_id':partner_id, 'jo_date':fields.Datetime.now(), 'pricelist_id':pricelist.id})
                current_charge_id = charge.id

            #Display Charge Form
            imd = self.env['ir.model.data']
            action = imd.xmlid_to_object('ejob_order.action_e_job_orders')
            tree_view_id = imd.xmlid_to_res_id('ejob_order.e_job_order_tree_view')
            form_view_id = imd.xmlid_to_res_id('ejob_order.e_job_order_form_view')

            result = {
                'name': action.name,
                'help': action.help,
                'type': action.type,
                'views': [[form_view_id, 'form'],[tree_view_id, 'tree']],
                'target': action.target,
                #'context': action.context,
                'res_model': action.res_model,
                'res_id': current_charge_id,
            }
            result['domain'] = "[('id','=',%s)]" % current_charge_id
            return result


    @api.multi
    def manage_payments(self):
        for rec in self:
            if rec.total_draft_charges > 0:
                partner_id = rec.id
                orders_obj = self.env['e.job.orders']
                #Check if the customer have a current (NEW) payment record
                payment_obj = self.env['ejob.cashier']
                new_payments = payment_obj.search([('partner_id','=',partner_id),('state','=',('new','inv'))])
                if new_payments:
                    current_payment_id = new_payments[0].id
                    #A NEW payment is already created, let's check for additional charges
                    orders = orders_obj.search([('partner_id', '=', partner_id),('state', '=', 'bill'), ('company_id', '=', self.env.user.company_id.id)])
                    for order in orders:
                        order.payment_id = current_payment_id
                else:
                    orders = orders_obj.search([('partner_id', '=', partner_id), ('state', '=', 'bill'), ('company_id', '=', self.env.user.company_id.id)])
                    if orders:
                        #payment_ref = self.env['ir.sequence'].next_by_code('eAC.payment.id')
                        payment_ref = 'NEW'
                        pricelist_id = rec.property_product_pricelist and rec.property_product_pricelist.id or orders[0].pricelist_id.id
                        payment_vals = {
                            'name': payment_ref,
                            'partner_id': partner_id,
                            'payment_date': fields.Datetime.now(),
                            'pricelist_id': pricelist_id,
                            'payment_type': 'Cash',
                        }
                        payment_id = payment_obj.create(payment_vals)
                        current_payment_id = payment_id.id
                        for order in orders:
                            order.payment_id = current_payment_id

                    else:
                        raise UserError('There are no Charges entered for this customer.')
                    #return {'type': 'ir.actions.act_window_close'}
                #update date last visit    
                rec.date_last_visit = fields.datetime.now()
                #Open Payment Entry Form
                imd = self.env['ir.model.data']
                action = imd.xmlid_to_object('ejob_order.action_ejob_cashier')
                form_view_id = imd.xmlid_to_res_id('ejob_order.ejob_soa_form_view')

                result = {
                    'name': action.name,
                    'help': action.help,
                    'type': action.type,
                    'views': [[form_view_id, 'form']],
                    'target': action.target,
                    #'context': action.context,
                    'res_model': action.res_model,
                    'res_id': current_payment_id,
                }
                result['domain'] = "[('id','=',%s)]" % current_payment_id
                return result
            else:
                raise UserError('Payment Record Creation Failed! No job orders entered for this customer.')
