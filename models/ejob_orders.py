# -*- coding : utf-8 -*-

from odoo.tools import float_is_zero
from odoo import models, fields, api, tools, _
from odoo.exceptions import Warning, UserError, ValidationError


class e_job_orders(models.Model):

    _name = "e.job.orders"
    _description = "Job Orders"
    _order = "id desc"

    @api.depends('services')
    def _compute_charges(self):
        if not self.ids:
            #Update calculated fields
            self.update({
                #'total_items_count': 0,
                'total_services_fee': 0.0,
            })
            return True

        for payment in self:
            #total_items_count = 0
            total_services_fee = 0.0
            #raise UserError('Debug: %s' % (list(table.pos_order_ids)))
            if payment.services:
                for charge in payment.services:
                    #for chargeline in charge.charge_line_ids:
                        #if chargeline.state == 'Done':
                        #total_items_count += 1
                    total_services_fee += charge.sub_total

            payment.update({
                #'total_items_count': total_items_count,
                'total_services_fee': total_services_fee,
            })

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

    @api.model
    def _get_default_stock_location(self):
        if self.env.user.employee_ids:
            employee = self.env.user.employee_ids[0]
            location_id = employee.department_id and employee.department_id.stock_location_id and employee.department_id.stock_location_id.id or False
            return location_id
        return False

    @api.model
    def _default_currency(self):
        return self.env.user.company_id.currency_id or None

    @api.model
    def _get_pricelist(self):
        return self.partner_id.property_product_pricelist or None

    #fields
    name = fields.Char('name')
    partner_id = fields.Many2one('res.partner',string='Customer')
    jo_date = fields.Date('Order Date', default=fields.Date.today())
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist')
    currency_id = fields.Many2one('res.currency', string='Currency', default=_default_currency)
    #maintenance_date = fields.Date('Maintenance Date')


    services = fields.One2many('ejob.service','ejob_orders_id',string='Services')

    total_services_fee = fields.Float(string='Net', compute='_compute_total_services')
    total_discount = fields.Float(string='Total Discount', compute='_compute_total_services')
    total_service_no_disc = fields.Float(string='Total Gross', compute='_compute_total_services')

    user_id = fields.Many2one ('res.users', 'Submitted by', required=True, readonly=True, default=lambda self: self.env.uid)
    procby_id = fields.Many2one('res.users', string='Processed by', readonly=True)

    location_id = fields.Many2one('stock.location', 'Stock Source',default=_get_default_stock_location)
    picking_type_id = fields.Many2one('stock.picking.type')
    payment_id = fields.Many2one('ejob.cashier','Payment')
    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=True, default=lambda self: self.env.user.company_id)
    state = fields.Selection([
        ('new','New'),
        ('submit','Submitted'),
        ('bill','Billed'),
        ('paid','Paid'),
        ('cancel','Cancelled'),], 'Status', default='new')
    #state = fields.Selection([('New','New'),('Submitted','Submitted'),('Done','Billed'),('Paid','Paid'),('Completed','Completed'),('Cancelled','Cancelled')],'Status',readonly=True,required=True,default='New')

    #ejob_cashier_id = fields.Many2one('ejob.cashier', ondelete='cascade')

    #@api.multi
    #def print_job_order(self):
    #    self.ensure_one()
    #    return self.env['report'].get_action(self, 'ejob_order.report_ejob_orders')


    @api.depends('services')
    def _compute_total_services(self):
        for rec in self:
            service_total = 0.0
            discount_total = 0.0
            net_no_disc_total = 0.0
            for line in rec.services:
                service_total += line.sub_total
                discount_total += line.discount_amount
                net_no_disc_total += line.net_no_disc
            rec.total_services_fee = rec.currency_id.round(service_total)
            rec.total_discount = rec.currency_id.round(discount_total)
            rec.total_service_no_disc = rec.currency_id.round(net_no_disc_total)


    @api.multi
    def process_service(self):
        for rec in self:
            if rec.state == 'new':
                rec.update({'state':'submit','procby_id':self.env.uid})
            else:
                raise UserError('ERROR! Only new services can be processed.')


    #validate job order
    @api.multi
    def validate_services(self):
        for rec in self:
            if rec.state == 'submit':
                prod_consu = any([x.id for x in rec.services if x.product_id.type in ['product', 'consu']])
                if prod_consu:
                    if not rec.location_id:
                        if self.env.user.employee_ids:
                            employee = self.env.user.employee_ids[0]
                            source_location_id = employee.department_id and employee.department_id.stock_location_id and employee.department_id.stock_location_id.id or None
                        else:
                            source_location_id = None
                            raise UserError('ERROR! Your account is not configured with a default stock location. Please contact your system administrator.')
                    else:
                        source_location_id = rec.location_id.id

                else:
                    source_location_id = None
                #Check QTY On Hand to ensure compliance with inventory
                #for line in rec.services:
                #    curr_qty = line.product_id.with_context({'location' : source_location_id}).qty_available
                #    if curr_qty < line.qty:
                #        raise UserError('ERROR! You do not have enough stock of "%s". QTY requested: %s, QTY available: %s.' % (rec.services.product_id.name, rec.services.qty, curr_qty))

                if source_location_id:
                    #Create stock moves
                    self.create_picking(source_location_id)

                rec.update({'state':'bill','location_id':source_location_id})
                rec.partner_id.date_last_visit = fields.datetime.now()
            else:
                raise UserError('ERROR! Only submitted orders can be validated.')
        self.env.user.notify_info('Orders are posted.',title='Services Validation', sticky=False)


    def create_picking(self,location_id):
        """Create a picking for each order and validate it."""
        Picking = self.env['stock.picking']
        Move = self.env['stock.move']
        StockWarehouse = self.env['stock.warehouse']
        for order in self:
            if not order.services.filtered(lambda l: l.product_id.type in ['product', 'consu']):
                continue
            address = order.partner_id.address_get(['delivery']) or {}
            picking_type = order.picking_type_id
            return_pick_type = order.picking_type_id.return_picking_type_id or order.picking_type_id
            order_picking = Picking
            return_picking = Picking
            moves = Move
            location_id = location_id #order.location_id.id
            if order.partner_id:
                destination_id = order.partner_id.property_stock_customer.id
            else:
                if (not picking_type) or (not picking_type.default_location_dest_id):
                    customerloc, supplierloc = StockWarehouse._get_partner_locations()
                    destination_id = customerloc.id
                else:
                    destination_id = picking_type.default_location_dest_id.id

            if picking_type:
                message = "This transfer has been created from the customer charges entry: <a href=# data-oe-model=e.job.orders data-oe-id=%d>%s</a>" % (order.id, order.name)
                picking_vals = {
                    'origin': order.name,
                    'partner_id': address.get('delivery', False),
                    'date_done': order.jo_date,
                    'picking_type_id': picking_type.id,
                    'company_id': order.company_id.id,
                    'move_type': 'direct',
                    'note': "",
                    'location_id': location_id,
                    'location_dest_id': destination_id,
                }
                pos_qty = any([x.qty > 0 for x in order.services if x.product_id.type in ['product', 'consu']])
                if pos_qty:
                    order_picking = Picking.create(picking_vals.copy())
                    order_picking.message_post(body=message)
                neg_qty = any([x.qty < 0 for x in order.services if x.product_id.type in ['product', 'consu']])
                if neg_qty:
                    return_vals = picking_vals.copy()
                    return_vals.update({
                        'location_id': destination_id,
                        'location_dest_id': return_pick_type != picking_type and return_pick_type.default_location_dest_id.id or location_id,
                        'picking_type_id': return_pick_type.id
                    })
                    return_picking = Picking.create(return_vals)
                    return_picking.message_post(body=message)

            for line in order.services.filtered(lambda l: l.product_id.type in ['product', 'consu'] and not float_is_zero(l.qty, precision_rounding=l.product_id.uom_id.rounding)):
                moves |= Move.create({
                    'name': 'ORD:' + line.product_id.name,
                    'origin': 'OUT:' + line.ejob_orders_id.name,
                    'product_uom': line.product_id.uom_id.id,
                    'picking_id': order_picking.id if line.qty >= 0 else return_picking.id,
                    'picking_type_id': picking_type.id if line.qty >= 0 else return_pick_type.id,
                    'product_id': line.product_id.id,
                    'product_uom_qty': abs(line.qty),
                    'state': 'draft',
                    'location_id': location_id if line.qty >= 0 else destination_id,
                    'location_dest_id': destination_id if line.qty >= 0 else return_pick_type != picking_type and return_pick_type.default_location_dest_id.id or location_id,
                })

            # prefer associating the regular order picking, not the return
            order.write({'picking_id': order_picking.id or return_picking.id})

            if return_picking:
                order._force_picking_done(return_picking)
            if order_picking:
                order._force_picking_done(order_picking)

            # when there are no picking_type_id set only the moves will be created
            if moves and not return_picking and not order_picking:
                tracked_moves = moves.filtered(lambda move: move.product_id.tracking != 'none')
                untracked_moves = moves - tracked_moves
                tracked_moves.action_confirm()
                untracked_moves.action_assign()
                moves.filtered(lambda m: m.state in ['confirmed', 'waiting']).force_assign()
                moves.filtered(lambda m: m.product_id.tracking == 'none').action_done()
        return True


    #cancel validation of job order
    @api.multi
    def cancel_invoice(self):
        for rec in self:
            if rec.state == 'bill':
                rec.state = 'submit'
                rec.procby_id = None
                rec.update({'state':'submit','procby_id':None})
                rec.payment_id.unlink()

                prod_consu = any([x.id for x in rec.services if x.product_id.type in ['product', 'consu']])
                if prod_consu:
                    if not rec.location_id:
                        if self.env.user.employee_ids:
                            employee = self.env.user.employee_ids[0]
                            source_location_id = employee.department_id and employee.department_id.stock_location_id and employee.department_id.stock_location_id.id or None
                        else:
                            source_location_id = None
                            raise UserError('ERROR! Your account is not configured with a default stock location. Please contact your system administrator.')
                    else:
                        source_location_id = rec.location_id.id
                else:
                    source_location_id = None
                if source_location_id:
                    #Create stock moves
                    self.create_undo_picking(source_location_id)
            else:
                raise UserError('ERROR! Only validated charges can be cancelled.')
        self.env.user.notify_info('Validation of charges are cancelled.',title='Validation Cancellation', sticky=False)

    def create_undo_picking(self,location_id):
        """Create a reverse picking for each order and validate it."""
        Picking = self.env['stock.picking']
        Move = self.env['stock.move']
        StockWarehouse = self.env['stock.warehouse']
        for order in self:
            if not order.services.filtered(lambda l: l.product_id.type in ['product', 'consu']):
                continue
            address = order.partner_id.address_get(['delivery']) or {}
            picking_type = order.picking_type_id
            return_pick_type = order.picking_type_id.return_picking_type_id or order.picking_type_id
            order_picking = Picking
            return_picking = Picking
            moves = Move
            location_id = location_id #order.location_id.id
            if order.partner_id:
                destination_id = order.partner_id.property_stock_customer.id
            else:
                if (not picking_type) or (not picking_type.default_location_dest_id):
                    customerloc, supplierloc = StockWarehouse._get_partner_locations()
                    destination_id = customerloc.id
                else:
                    destination_id = picking_type.default_location_dest_id.id

            if picking_type:
                message = "This reverted transfer has been created from the customer services entry: <a href=# data-oe-model=e.job.orders data-oe-id=%d>%s</a>" % (order.id, order.name)
                picking_vals = {
                    'origin': order.name,
                    'partner_id': address.get('delivery', False),
                    'date_done': order.jo_date,
                    'picking_type_id': picking_type.id,
                    'company_id': order.company_id.id,
                    'move_type': 'direct',
                    'note': "",
                    'location_id': location_id,
                    'location_dest_id': destination_id,
                }
                pos_qty = any([x.qty > 0 for x in order.services if x.product_id.type in ['product', 'consu']])
                if pos_qty:
                    order_picking = Picking.create(picking_vals.copy())
                    order_picking.message_post(body=message)
                neg_qty = any([x.qty < 0 for x in order.services if x.product_id.type in ['product', 'consu']])
                if neg_qty:
                    return_vals = picking_vals.copy()
                    return_vals.update({
                        'location_id': destination_id,
                        'location_dest_id': return_pick_type != picking_type and return_pick_type.default_location_dest_id.id or location_id,
                        'picking_type_id': return_pick_type.id
                    })
                    return_picking = Picking.create(return_vals)
                    return_picking.message_post(body=message)

            for line in order.services.filtered(lambda l: l.product_id.type in ['product', 'consu'] and not float_is_zero(l.qty, precision_rounding=l.product_id.uom_id.rounding)):
                moves |= Move.create({
                    'name': line.name,
                    'product_uom': line.product_id.uom_id.id,
                    'picking_id': order_picking.id if line.qty <= 0 else return_picking.id,
                    'picking_type_id': picking_type.id if line.qty <= 0 else return_pick_type.id,
                    'product_id': line.product_id.id,
                    'product_uom_qty': abs(line.qty),
                    'state': 'draft',
                    'location_id': location_id if line.qty <= 0 else destination_id,
                    'location_dest_id': destination_id if line.qty <= 0 else return_pick_type != picking_type and return_pick_type.default_location_dest_id.id or location_id,
                })

            # prefer associating the return picking, not the regular order
            order.write({'undo_picking_id': return_picking.id or order_picking.id })

            if return_picking:
                order._force_picking_done(return_picking)
            if order_picking:
                order._force_picking_done(order_picking)

            # when there are no picking_type_id set only the moves will be created
            if moves and not return_picking and not order_picking:
                tracked_moves = moves.filtered(lambda move: move.product_id.tracking != 'none')
                untracked_moves = moves - tracked_moves
                tracked_moves.action_confirm()
                untracked_moves.action_assign()
                moves.filtered(lambda m: m.state in ['confirmed', 'waiting']).force_assign()
                moves.filtered(lambda m: m.product_id.tracking == 'none').action_done()
        return True

    def _force_picking_done(self, picking):
        """Force picking in order to be set as done."""
        self.ensure_one()
        contains_tracked_products = any([(product_id.tracking != 'none') for product_id in self.services.mapped('product_id')])

        # do not reserve for tracked products, the user will have manually specified the serial/lot numbers
        if contains_tracked_products:
            picking.action_confirm()
        else:
            picking.action_assign()

        picking.force_assign()
        #self.set_pack_operation_lot(picking)
        if not contains_tracked_products:
            picking.action_done()

    @api.multi
    def manage_charge_slip_payment(self):
        for rec in self:
            if rec.total_services_fee > 0:
                partner_id = rec.partner_id.id
                #Check if the customer have a current (NEW) payment record
                payment_obj = self.env['ejob.cashier']
                if rec.payment_id:
                    current_payment_id = rec.payment_id.id
                else:
                    payment_ref = 'NEW'
                    pricelist_id = rec.partner_id.property_product_pricelist and rec.partner_id.property_product_pricelist.id or rec.payment_id.pricelist_id.id
                    payment_vals = {
                        'name': payment_ref,
                        'partner_id': partner_id,
                        'payment_date': fields.Datetime.now(),
                        'pricelist_id': pricelist_id,
                        'payment_type': 'Charge Slip',
                    }
                    payment_id = payment_obj.create(payment_vals)
                    current_payment_id = payment_id.id
                    rec.payment_id = current_payment_id

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
                raise UserError('Payment Record Creation Failed! No charges entered for this customer.')
        self.env.user.notify_info('Charge slip payments are processed. Continue with the validation in the form that opened.',title='Payment Processing', sticky=False)


class ejob_service(models.Model):

    _name = "ejob.service"
    _description = "Service"

    @api.model
    def _get_default_stock_location(self):
        if self.env.user.employee_ids:
            employee = self.env.user.employee_ids[0]
            location_id = employee.department_id and employee.department_id.stock_location_id and employee.department_id.stock_location_id.id or False
            return location_id
        return False

    name = fields.Char('Service Ref')
    product_id = fields.Many2one('product.product', string="Product Name")
    description= fields.Char(string='Description')
    price_unit =fields.Float(string='Unit Price' , digits=(12,2), default=0.0)
    price_unit2 = fields.Float(string='Unit Price', digits=(12,2), default=0.0)
    qty = fields.Float(string='Qty', digits=(8,2), default=1.0)
    discount_percentage = fields.Float(string="Discount(%)", digits=(3,2))
    discount_amount = fields.Float(string='Discount', compute='_compute_discount_amount')
    net_no_disc = fields.Float(string='Gross', compute='_compute_total_price')
    sub_total = fields.Float(string='Net', compute='_compute_total_price')
    location_id = fields.Many2one('stock.location', 'Stock Source', default=_get_default_stock_location, domain=[('usage', '=', 'internal')])
    ejob_orders_id = fields.Many2one('e.job.orders',  string='Customer Services', ondelete='cascade')

    @api.model
    def create(self, vals):
        if not vals.get('name',False):
            vals['name'] = self.ejob_orders_id.name or 'NEW'
        result = super(ejob_service, self).create(vals)
        return result

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            if not self.ejob_orders_id.pricelist_id:
                raise UserError(
                    _('You have to select a pricelist!\n'
                      'Please set one before choosing a product.'))
            price = self.ejob_orders_id.pricelist_id.get_product_price(
                self.product_id, self.qty or 1.0, self.ejob_orders_id.partner_id)
            self._onchange_qty()
            self.price_unit = price
            self.price_unit2 = price

    @api.depends('qty','price_unit','discount_percentage')
    def _compute_discount_amount(self):
        for rec in self:
            disc = rec.price_unit * rec.qty * (rec.discount_percentage / 100)
            rec.update({
                'discount_amount': round(disc,2),
            })


    @api.onchange('qty', 'price_unit2')
    def _onchange_qty(self):
        if self.product_id:
            #Check if the product is stockable and determine if the stock location have enough QTY to Dispense
            if self.product_id.type == 'product':
                if self.location_id:
                    curr_qty = self.product_id.with_context({'location' : self.location_id.id}).qty_available
                    if curr_qty < self.qty:
                        raise UserError('ERROR! You do not have enough stock of "%s". QTY requested: %s, QTY available: %s' % (self.product_id.name, self.qty, curr_qty))
                else:
                    raise UserError('ERROR! A stock location is needed for the product you selected.')
            self.price_unit2 = self.price_unit
            #self.price_unit = self.price_unit2
            if not self.ejob_orders_id.pricelist_id:
                raise UserError(_('You have to select a pricelist!'))
            #price = self.unit_price2
            #self.total_price = price * self.qty

    @api.depends('product_id','price_unit','price_unit2','qty', 'discount_amount')
    def _compute_total_price(self):
        for rec in self:
            net = rec.price_unit * rec.qty - rec.discount_amount
            net_no_disc = rec.price_unit * rec.qty
            rec.update({
                'sub_total': round(net,2),
                'net_no_disc': round(net_no_disc,2),
            })
