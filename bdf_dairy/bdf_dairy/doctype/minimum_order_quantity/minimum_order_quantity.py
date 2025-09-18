# Copyright (c) 2024, BDF and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class MinimumOrderQuantity(Document):
	def before_save(self):
		for cust in self.customers:
			duplicate_entry = frappe.db.sql("""
				SELECT
					customer, parent
				FROM
					`tabMOQ Customer`  
				WHERE
					customer = %s
				LIMIT 1
			""", (cust.customer), as_dict=True)
			if duplicate_entry and duplicate_entry[0]['parent'] != self.name:
				frappe.throw(
					f"Duplicate Entry Cannot Be Made For Customer: {cust.customer} with MOQ ID: {duplicate_entry[0]['parent']}"
				)

			
		unique_combinations = set()
		for moq in self.moq_details:
			combination = (moq.item, moq.uom)
			if combination in unique_combinations:
				frappe.throw(f"Duplicate entry found for Item: {moq.item} and UOM: {moq.uom}. Each combination must be unique.")
			
			unique_combinations.add(combination)

	@frappe.whitelist() 
	def get_all_customer(self):
		self.customers.clear()
		for cust in frappe.get_all("Customer", {'customer_group': self.customer_group, 'disabled': 0}):
			self.append('customers',{'customer': cust.name, 'customer_name': frappe.db.get_value("Customer", cust.name, 'customer_name')})