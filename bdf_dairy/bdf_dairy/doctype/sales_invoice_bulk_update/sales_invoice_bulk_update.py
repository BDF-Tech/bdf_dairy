# Copyright (c) 2025, BDF and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class SalesInvoiceBulkUpdate(Document):
	def before_save(self):
		if self.posting_date and self.payment_due_date:
			if self.payment_due_date <= self.posting_date :
				frappe.throw("Due Date cannot be before Posting / Supplier Invoice Date")

	@frappe.whitelist()
	def get_sales_invoices_date(self):
		if self.from_date and self.to_date:
			sale = frappe.get_list("Sales Invoice", 
						filters={"posting_date": ["between", [self.from_date, self.to_date]], "docstatus":0, 'route': self.route, 'delivery_shift': self.shift},
						fields=["name","posting_date","posting_time","due_date","customer","customer_name"])
			if not sale:
				frappe.throw("Data Not Found.")
			for d in sale:
				self.append('date_update',{
					"invoice_no":d.name,
					"posting_date":d.posting_date,
					"posting_time" :d.posting_time,
					"payment_due_date":d.due_date,
					"customer":d.customer,
					"customer_name":d.customer_name
				})

	def on_submit(self):
		for i in self.get("date_update", {"check": 1}):
			try:
				sales_inv = frappe.get_doc("Sales Invoice", i.invoice_no)
				if self.posting_date and self.posting_time and self.payment_due_date:
					sales_inv.set_posting_time = 1
					sales_inv.posting_date = self.posting_date
					sales_inv.posting_time = self.posting_time
					sales_inv.due_date = self.payment_due_date

					for term in sales_inv.get("payment_schedule", []):
						term.due_date = self.payment_due_date

				sales_inv.save()
				sales_inv.submit()

			except Exception as e:
				frappe.log_error(frappe.get_traceback(), f"Error in invoice {i.invoice_no}")
				frappe.throw(f"Error while processing Sales Invoice <b>{i.invoice_no}</b>: {str(e)}")


	@frappe.whitelist()
	def selectall(self):
		children = self.get('date_update')
		if not children:
			return
		all_selected = all([child.check for child in children])  
		value = 0 if all_selected else 1 
		for child in children:
			child.check = value
