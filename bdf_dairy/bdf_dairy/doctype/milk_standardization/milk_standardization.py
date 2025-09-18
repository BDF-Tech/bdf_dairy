# Copyright (c) 2025, BDF and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class MilkStandardization(Document):
	def before_submit(self):
		self.create_repack_entry()

	def create_repack_entry(self):
		stock_entry = frappe.new_doc("Stock Entry")
		stock_entry_type = frappe.get_value("Stock Entry Type", {"purpose": "Repack", "is_standard": 1})
		stock_entry.stock_entry_type = stock_entry_type
		stock_entry.purpose = "Repack"
		stock_entry.company = self.company
		stock_entry.from_warehouse = self.dmc
		stock_entry.to_warehouse = self.target_warehouse
		stock_entry.posting_date = self.date
		stock_entry.set_posting_time = 1
		stock_entry.custom_milk_standardization = self.name

		stock_entry.append("items", {
			"item_code": self.standard_finished_item,
			"qty": self.total_qty,
			"uom": self.finished_item_uom,
			"t_warehouse":self.target_warehouse
		})
		for d in self.milk_standardization_details:
			item_row = stock_entry.append("items", {})
			item_row.item_code = d.item
			item_row.qty = d.qty
			item_row.uom = d.uom
			item_row.stock_uom = d.uom
			item_row.s_warehouse = d.source_warehouse
			item_row.conversion_factor = 1

		stock_entry.insert(ignore_permissions=True)
		stock_entry.submit()

		frappe.msgprint(f"Repack Stock Entry <b>{stock_entry.name}</b> created.")
		return stock_entry.name
