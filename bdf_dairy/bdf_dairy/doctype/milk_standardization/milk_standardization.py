# Copyright (c) 2025, BDF and contributors
# For license information, please see license.txt

import frappe







# from frappe.model.document import Document
# from erpnext.stock.utils import get_stock_balance

# class MilkStandardization(Document):
# 	def before_submit(self):
# 		for i in self.items:
# 			if i.required_item and not i.item_code:
# 				frappe.throw(f"Row {i.idx}: Item Code Required")
# 		self.create_manufacturing_entry()

# 	def add_or_update_item(self, item_type, qty, required_item=0):
# 		existing = None
# 		for d in self.items:
# 			if d.type == item_type:
# 				existing = d
# 				break

# 		if existing:
# 			existing.quantity = qty
# 			if not existing.actual_quantity:
# 				existing.actual_quantity = qty

# 		else:
# 			self.append("items", {
# 				"type": item_type,
# 				"quantity": qty,
# 				"actual_quantity": qty,
# 				"required_item": required_item,
# 			})


# 	def before_save(self):
# 		raw_milk_req_kg, smp_req_kg, water_req_kg, check_final_fat, check_final_snf, balance_kg, balance_ltr = 0, 0, 0, 0, 0, 0, 0
# 		denominator = ((self.raw_fat/100)*(self.smp_snf/100) - (self.raw_snf/100)*(self.smp_fat/100))
# 		if denominator == 0:
# 			frappe.throw("Invalid values for FAT/SNF calculation. Please check inputs.")
# 		raw_milk_req_kg = (((self.milk_kg*self.fat)/100)*(self.smp_snf/100) - ((self.milk_kg*self.snf)/100)*(self.smp_fat/100)) / denominator
# 		smp_req_kg = (((self.milk_kg*self.snf)/100)*(self.raw_fat/100) - ((self.milk_kg*self.fat)/100)*(self.raw_snf/100)) / denominator
# 		water_req_kg = self.milk_kg - raw_milk_req_kg - smp_req_kg
# 		check_final_fat = (((self.raw_fat/100)*raw_milk_req_kg + (self.smp_fat/100)*smp_req_kg) / self.milk_kg) * 100
# 		check_final_snf = (((self.raw_snf/100)*raw_milk_req_kg + (self.smp_snf/100)*smp_req_kg) / self.milk_kg) * 100
# 		balance_kg = raw_milk_req_kg + smp_req_kg + water_req_kg
# 		balance_ltr = balance_kg * 0.9707

# 		self.add_or_update_item("Raw Milk Required Kg", raw_milk_req_kg, 1)
# 		self.add_or_update_item("SMP Required Kg", smp_req_kg, 1)
# 		self.add_or_update_item("Water Required Kg", water_req_kg, 1)
# 		self.add_or_update_item("Check Final FAT PCT", check_final_fat)
# 		self.add_or_update_item("Check Final SNF PCT", check_final_snf)
# 		self.add_or_update_item("Mass Balance Kg", balance_kg)
# 		self.add_or_update_item("Mass Balance Litre", balance_ltr)

		
# 	def create_manufacturing_entry(self):
# 		stock_entry = frappe.new_doc("Stock Entry")

# 		stock_entry_type = frappe.get_value("Stock Entry Type", {"purpose": "Manufacture", "is_standard": 1}, "name")
# 		if not stock_entry_type:
# 			frappe.throw("No standard Stock Entry Type found for Manufacture.")

# 		stock_entry.stock_entry_type = stock_entry_type
# 		stock_entry.purpose = "Manufacture"
# 		stock_entry.company = self.company
# 		stock_entry.from_warehouse = self.dmc
# 		stock_entry.to_warehouse = self.target_warehouse
# 		stock_entry.posting_date = self.date
# 		stock_entry.set_posting_time = 1
# 		stock_entry.custom_milk_standardization = self.name

# 		# Finished item
# 		stock_entry.append("items", {
# 			"item_code": self.finished_item,
# 			"qty": self.milk_ltr,
# 			"uom": self.uom,
# 			"t_warehouse": self.target_warehouse,
# 			"is_finished_item": 1
# 		})

# 		# Raw material consumption
# 		for d in self.items:   # assuming 'items' child table is used
# 			if d.required_item and d.item_code:
# 				item_row = stock_entry.append("items", {})
# 				item_row.item_code = d.item_code
# 				item_row.qty = d.actual_quantity
# 				item_row.uom = d.uom
# 				item_row.s_warehouse = d.source_warehouse
# 				item_row.conversion_factor = 1

# 		stock_entry.insert(ignore_permissions=True, ignore_mandatory=True)
# 		stock_entry.submit()

# 		frappe.msgprint(f"Manufacturing Stock Entry <b>{stock_entry.name}</b> created.")

# 	def create_repack_entry(self):
# 		stock_entry = frappe.new_doc("Stock Entry")
# 		stock_entry_type = frappe.get_value("Stock Entry Type", {"purpose": "Repack", "is_standard": 1})
# 		stock_entry.stock_entry_type = stock_entry_type
# 		stock_entry.purpose = "Repack"
# 		stock_entry.company = self.company
# 		stock_entry.from_warehouse = self.dmc
# 		stock_entry.to_warehouse = self.target_warehouse
# 		stock_entry.posting_date = self.date
# 		stock_entry.set_posting_time = 1
# 		stock_entry.custom_milk_standardization = self.name

# 		stock_entry.append("items", {
# 			"item_code": self.standard_finished_item,
# 			"qty": self.total_qty,
# 			"uom": self.finished_item_uom,
# 			"t_warehouse":self.target_warehouse
# 		})
# 		for d in self.milk_standardization_details:
# 			item_row = stock_entry.append("items", {})
# 			item_row.item_code = d.item
# 			item_row.qty = d.qty
# 			item_row.uom = d.uom
# 			item_row.stock_uom = d.uom
# 			item_row.s_warehouse = d.source_warehouse
# 			item_row.conversion_factor = 1

# 		stock_entry.insert(ignore_permissions=True)
# 		stock_entry.submit()

# 		frappe.msgprint(f"Repack Stock Entry <b>{stock_entry.name}</b> created.")
# 		return stock_entry.name
