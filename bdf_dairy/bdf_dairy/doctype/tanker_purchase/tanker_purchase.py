# Copyright (c) 2025, BDF and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt
from frappe.model.document import Document

class TankerPurchase(Document):
	def get_item(self):
		item = None
		if self.milk_type == "Cow":
			item = frappe.db.get_single_value("Dairy Settings", "cow_pro")
		elif self.milk_type == "Buffalo":
			item = frappe.db.get_single_value("Dairy Settings", "buf_pro")
		elif self.milk_type == "Mix":
			item = frappe.db.get_single_value("Dairy Settings", "mix_pro")
		else:
			frappe.throw("Set Milk Type")
		return item
 
	def before_save(self):
		item = self.get_item()
		item_name = frappe.get_value("Item", item,'item_name')
		total_quantity = 0
		total_amount = 0
		total_kg_fat = 0
		total_kg_snf = 0
		total_fat = 0
		total_snf = 0
		count = 0

		for row in self.tanker_purchase_details:
			total_quantity += flt(row.quantity)
			total_amount += flt(row.amount)
			total_kg_fat += flt(row.kg_fat)
			total_kg_snf += flt(row.kg_snf)
			total_fat += flt(row.fat)
			total_snf += flt(row.snf)
			count += 1

		# Set totals
		self.total_quantity = total_quantity
		self.total_amount = total_amount
		self.total_kg_fat = total_kg_fat
		self.total_kg_snf = total_kg_snf

		# Set averages (safe division)
		self.avg_fat = (total_fat / count) if count else 0
		self.avg_snf = (total_snf / count) if count else 0

		self.tanker_purchase_and_milk_entry_difference.clear()
		for p in self.milk_entry_details:
			self.append('tanker_purchase_and_milk_entry_difference', {
				'item': p.item,
				'item_name': p.item_name,
				'quantity': self.total_quantity - p.quantity,
				'quantity_kg': (self.total_quantity * 1.03) - p.quantity_kg,
				'fat': self.avg_fat - p.fat,
				'snf': self.avg_snf - p.snf,
				'kg_fat': self.total_kg_fat - p.kg_fat,
				'kg_snf': self.total_kg_snf - p.kg_snf,
				'rate': (self.total_amount / self.total_quantity) - p.rate if self.total_quantity else 0,
				'amount': self.total_amount - p.amount
			})



	@frappe.whitelist()
	def fetch_milk_entry_data(self):
		self.milk_entry_details.clear()

		if not self.dcs:
			frappe.throw("DCS is Missing")

		if not self.shift:
			frappe.throw("Shift is Missing")

		if not self.supplier:
			frappe.throw("Supplier is Missing")

		filters = {'dcs_id': self.dcs, 'shift': self.shift, 'date': self.purchase_date,
					'member': self.supplier, 'milk_type': self.milk_type}
		fields = ['volume', 'fat', 'snf', 'unit_price']
		milk_entries = frappe.get_all("Milk Entry", filters=filters, fields=fields)

		item = self.get_item()
		item_name = frappe.get_value("Item", item,'item_name')
		for m in milk_entries:
			self.append('milk_entry_details', {
				'item': item,
				'item_name': item_name,
				'quantity': m.volume,
				'quantity_kg': m.volume * 1.03,
				'fat': m.fat,
				'snf': m.snf,
				'kg_fat': ((m.volume * 1.03) * m.fat / 100),
				'kg_snf': ((m.volume * 1.03) * m.snf / 100),
				'rate': m.unit_price,
				'amount': m.unit_price * m.volume
			})
