# -*- coding: utf-8 -*-
import time
from odoo import models, fields, api, _

class ReporteJobOrder(models.AbstractModel):
	_name = 'report.ejob_order.report_ejob_orders_view'

	def get_soa_data(self,data):
		lst = []
		order_search = self.env['e.job.orders'].search(
			[('parent_id','=',data['parent_id'][0]),
			 ('jo_date','>=',data['start_date']),
			 ('jo_date','<=',data['end_date'])],
			order='name desc')
		res = ()
		self.total_ = 0
		for soa in student_search:
			self.total_student +=1
			res= {
				'name' : soa.student_id.display_name,
				'order_id' : soa.order_id.display_name,
				'product_id' : soa.product_id.display_name,
				'amount' : soa.amount,
				'date' : soa.date,
			}
			lst.append(res)
		return lst

	def get_invoice_data(self,data):
		lst = []
		inv_search = self.env['account.invoice'].search(
			[('partner_id','=',data['student_id'][0]),
			 ('date_invoice','>=', data['start_date']),
			 ('date_invoice','<=', data['end_date'])],
			order='origin asc')
		res = ()
		self.total_inv = 0
		for inv in inv_search:
			self.total_inv +=1
			res={
				'origin' : inv.origin,
				'or_number' : inv.or_number,
				'date' : inv.date_invoice,
				'total' : inv.amount_total_signed,
				'status' : inv.state,
			}
			lst.append(res)
		return lst

	def get_order_data(self,data):
		lst = []
		order_search = self.env['sale.order'].search(
			[('partner_id','=',data['student_id'][0]),
			 ('date_order','>=',data['start_date']),
			 ('date_order','<=',data['end_date'])],
			order='name asc')
		res = ()
		self.total_order = 0
		for order in order_search:
			self.total_order += 1
			res={
				'ref' : order.name,
				'date' : order.date_order,
				'status' : order.invoice_status,
			}
			lst.append(res)
		return lst



	@api.model
	def render_html(self, docids, data=None):
		model = self.env.context.get('active_model')
		docs = self.env[model].browse(self.env.context.get('active_id'))
		docargs = {
			'doc_ids' : self.ids,
			'doc_model' : model,
			'docs' : docs,
			'time' : time,
			'data' : data,
			'start_date' : data['start_date'],
			'end_date' : data['end_date'],
			'get_soa_data' : self.get_soa_data(data),
			'get_invoice_data' : self.get_invoice_data(data),
			'get_order_data' : self.get_order_data(data),
		}
		return self.env['report'] \
			.render('ejob_order.report_ejob_orders_view', docargs)
