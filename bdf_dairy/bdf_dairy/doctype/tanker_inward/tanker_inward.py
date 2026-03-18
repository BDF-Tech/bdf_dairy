import frappe
from frappe.model.document import Document
from frappe.utils import flt

class TankerInward(Document):
	def before_submit(self):
		diff_qty = 0
		for diff in self.get('difference_of_dcs_and_tanker_milk_received', filters={'qty_in_liter': ['>', 0]}):
			diff_qty += diff.qty_in_liter
		for diff in self.get('difference_of_dcs_and_tanker_milk_received', filters={'qty_in_liter': ['<', 0]}):
			diff_qty += diff.qty_in_liter

		if self.si_qty_in_liter < 0 and not self.sales_item:
			frappe.throw("Sales Item is Mandatory")

		if diff_qty > 0 and not self.excess_warehouse:
			frappe.throw("Difference is Posotive. So Excess Warehouse Is Mandatory")
		if diff_qty < 0 and not self.loss_warehouse:
			frappe.throw("Difference is Negative. So Loss Warehouse Is Mandatory")

		self.material_transfer_from_dcs_to_tanker()  
		
		if self.si_qty_in_liter > 0:
			self.material_transfer_from_tanker_to_sales()
		if self.sr_qty_in_liter > 0:
			self.material_transfer_from_sales_to_tanker()

		self.material_transfer_from_tanker_to_plant(round(diff_qty, 3))
		if diff_qty > 0:
			self.material_receipt_to_excess(round(diff_qty, 3))
		if diff_qty < 0:
			self.material_transfer_from_tanker_to_loss(round(abs(diff_qty), 3))

	def material_receipt_to_tanker(self, qty):
		self.create_stock_entry(
			stock_entry_type="Material Receipt",
			items=[{
				"item_code": self.get_item(),
				"qty": qty,
				"t_warehouse": self.tanker_warehouse
			}],
			user_remark = self.vehicle_number
		)
	
	def material_receipt_to_excess(self, qty):
		self.create_stock_entry(
			stock_entry_type="Material Receipt",
			items=[{
				"item_code": self.get_item(),
				"qty": qty,
				"t_warehouse": self.excess_warehouse
			}],
			user_remark = self.vehicle_number
		)

	@frappe.whitelist()
	def material_transfer_from_dcs_to_tanker(self):
		items = []
		for itm in self.get('milk_received_from_dcs'):
			items.append({
				"item_code": self.get_item(),
				"qty": itm.qty_in_liter,
				"s_warehouse": itm.dcs,
				"t_warehouse": self.tanker_warehouse
			})
		self.create_stock_entry(stock_entry_type="Material Transfer", items=items)

	@frappe.whitelist()
	def material_transfer_from_tanker_to_plant(self, qty=0):
		items = []
		for itm in self.get('milk_received_from_tanker'):
			items.append({
				"item_code": self.get_item(),
				"qty": itm.qty_in_liter,
				"s_warehouse": self.tanker_warehouse,
				"t_warehouse": self.plant_warehouse
			})
		self.create_stock_entry(stock_entry_type="Material Transfer", items=items)

	@frappe.whitelist()
	def material_transfer_from_tanker_to_sales(self):
		items = []
		items.append({
			"item_code": self.get_item(),
			"qty": self.si_qty_in_liter,
			"s_warehouse": self.tanker_warehouse,
		})
		items.append({
			"item_code": self.sales_item,
			"qty": self.si_qty_in_liter,
			"t_warehouse": self.si_dcs
		})
		self.create_stock_entry(stock_entry_type="Repack", items=items)

	@frappe.whitelist()
	def material_transfer_from_sales_to_tanker(self):
		items = []
		items.append({
			"item_code": self.sales_item,
			"qty": self.sr_qty_in_liter,
			"s_warehouse": self.si_dcs,
		})
		items.append({
			"item_code": self.get_item(),
			"qty": self.sr_qty_in_liter,
			"t_warehouse": self.tanker_warehouse
		})
		self.create_stock_entry(stock_entry_type="Repack", items=items)

	@frappe.whitelist()
	def material_transfer_from_tanker_to_loss(self, qty):
		items = []
		items.append({
			"item_code": self.get_item(),
			"qty": qty,
			"s_warehouse": self.tanker_warehouse,
			"t_warehouse": self.loss_warehouse
		})
		self.create_stock_entry(stock_entry_type="Material Transfer", items=items)

	@frappe.whitelist()
	def material_transfer_from_tanker_to_excess(self, qty):
		items = []
		items.append({
			"item_code": self.get_item(),
			"qty": qty,
			"s_warehouse": self.tanker_warehouse,
			"t_warehouse": self.excess_warehouse
		})
		self.create_stock_entry(stock_entry_type="Material Transfer", items=items)

	def create_stock_entry(self, stock_entry_type, items, user_remark = None):
		# try:
		stock_entry = frappe.new_doc("Stock Entry")
		stock_entry.stock_entry_type = stock_entry_type

		for item in items:
			stock_entry.append("items", item)
		stock_entry.custom_tanker_inward = self.name
		if user_remark:
			stock_entry.custom_user_remark = user_remark
		stock_entry.save()
		stock_entry.submit()

	@frappe.whitelist()
	def get_material_receipt(self):
		diff_qty = 0
		for diff in self.get('difference_of_dcs_and_tanker_milk_received', filters={'qty_in_liter': ['>', 0]}):
			diff_qty += diff.qty_in_liter
		return diff_qty

	def before_save(self):
		if self.si_qty_in_liter < self.sr_qty_in_liter:
			frappe.throw(f"Return Qty Can Not Greater Than Sales Qty.")

		qty_liter = (self.total_qty_in_liter or 0) - (self.si_qty_in_liter or 0) + (self.sr_qty_in_liter or 0)
		fat = (self.fat or 0) - (self.si_fat or 0) + (self.sr_fat or 0)
		snf = (self.snf or 0) - (self.si_snf or 0) + (self.sr_snf or 0)
		kg_fat = (self.kg_fat or 0) - (self.si_kg_fat or 0) + (self.sr_kg_fat or 0)
		kg_snf = (self.kg_snf or 0) - (self.si_kg_snf or 0) + (self.sr_kg_snf or 0)

		for m in self.milk_received_from_tanker:
			qty_liter = (m.qty_in_liter or 0) - qty_liter
			fat = (m.fat or 0) - fat
			snf = (m.snf or 0) - snf
			kg_fat = (m.kg_fat or 0) - kg_fat
			kg_snf = (m.kg_snf or 0) - kg_snf

		self.difference_of_dcs_and_tanker_milk_received.clear()
		diff_row = self.append("difference_of_dcs_and_tanker_milk_received", {})
		diff_row.dcs = self.dcs
		diff_row.qty_in_liter = qty_liter
		diff_row.qty_in_kg = qty_liter * 1.03
		diff_row.fat = fat
		diff_row.kg_fat = kg_fat
		diff_row.snf = snf
		diff_row.kg_snf = kg_snf
	
		# ============================
# 🔴 ADD OTHER TANKER VALUES
# ============================

		other_litre = self.total_qty_in_litre1 or 0
		other_kg = self.total_qty_in_kg1 or 0
		other_kg_fat = self.kg_fat1 or 0
		other_kg_snf = self.kg_snf1 or 0

		# ============================
		# 🔴 CURRENT (DCS VALUES)
		# ============================

		dcs_litre = self.total_qty_in_liter or 0
		dcs_kg = self.total_qty_in_kg or 0
		dcs_kg_fat = self.kg_fat or 0
		dcs_kg_snf = self.kg_snf or 0

		# ============================
		# 🔴 FINAL COMBINE
		# ============================

		final_litre = dcs_litre + other_litre
		final_kg = dcs_kg + other_kg
		final_kg_fat = dcs_kg_fat + other_kg_fat
		final_kg_snf = dcs_kg_snf + other_kg_snf

		if final_kg > 0:
			final_fat = (final_kg_fat / final_kg) * 100
			final_snf = (final_kg_snf / final_kg) * 100
		else:
			final_fat = 0
			final_snf = 0

# ============================
# 🔴 SET FINAL VALUES
# ============================

		self.total_qty_in_liter = final_litre
		self.total_qty_in_kg = final_kg
		self.kg_fat = final_kg_fat
		self.kg_snf = final_kg_snf
		self.fat = final_fat
		self.snf = final_snf
	@frappe.whitelist()
	def get_milk_entry_data(self):
		date_range_query = """
			WITH RECURSIVE DateRange AS (
				SELECT %s AS date  -- Start date
				UNION ALL
				SELECT DATE_ADD(date, INTERVAL 1 DAY)
				FROM DateRange
				WHERE date < %s     -- End date
			)
			SELECT date FROM DateRange;
		"""
		date_params = (self.from_date, self.to_date)
		all_dates = frappe.db.sql(date_range_query, date_params, as_dict=True)
		date_shift_list = []
		n = len(all_dates)

		def shift_exists(date_shift_list, date, shift):
			return any(entry['date'] == date and entry['shift'] == shift for entry in date_shift_list)

		for row in range(n):
			current_date = all_dates[row]['date']
			if self.from_date == self.to_date and self.from_shift == "Morning" and self.to_shift == "Morning":
				if not shift_exists(date_shift_list, current_date, "Morning"):
					date_shift_list.append({"date": current_date, "shift": "Morning"})
				break 

			if row == 0:
				if self.from_shift == "Morning":
					if not shift_exists(date_shift_list, current_date, "Morning"):
						date_shift_list.append({"date": current_date, "shift": "Morning"})
					if not shift_exists(date_shift_list, current_date, "Evening"):
						date_shift_list.append({"date": current_date, "shift": "Evening"})
				elif self.from_shift == "Evening":
					if not shift_exists(date_shift_list, current_date, "Evening"):
						date_shift_list.append({"date": current_date, "shift": "Evening"})

			elif row == n - 1:
				if self.to_shift == "Morning":
					if not shift_exists(date_shift_list, current_date, "Morning"):
						date_shift_list.append({"date": current_date, "shift": "Morning"})
				elif self.to_shift == "Evening":
					if not shift_exists(date_shift_list, current_date, "Morning"):
						date_shift_list.append({"date": current_date, "shift": "Morning"})
					if not shift_exists(date_shift_list, current_date, "Evening"):
						date_shift_list.append({"date": current_date, "shift": "Evening"})

			else:
				if not shift_exists(date_shift_list, current_date, "Morning"):
					date_shift_list.append({"date": current_date, "shift": "Morning"})
				if not shift_exists(date_shift_list, current_date, "Evening"):
					date_shift_list.append({"date": current_date, "shift": "Evening"})


		dcs_data = {}

		for param in date_shift_list:
			milk_entry_sql_query = """
				SELECT 
					dcs_id as dcs,
					date as date,
					shift as shift,
					SUM(volume) as ack_liter,
					SUM(volume * 1.03) as ack_kg,
					((SUM(fat_kg) / SUM(volume * 1.03)) * 100) as ack_fat,
					((SUM(snf_kg) / SUM(volume * 1.03)) * 100) as ack_snf,
					SUM(fat_kg) as ack_kg_fat,
					SUM(snf_kg) as ack_kg_snf
				FROM 
					`tabMilk Entry`
				WHERE 
					date = %s 
					AND shift = %s
					AND dcs_id = %s
					AND docstatus = 1
					AND milk_type = %s
				GROUP BY 
					date, shift, dcs_id
			"""
			milk_data = frappe.db.sql(milk_entry_sql_query, (param['date'], param['shift'], self.dcs, self.milk_type), as_dict=True)

			for data in milk_data:
				key = (data['dcs'], data['date'], data['shift'])  
				if key not in dcs_data:
					dcs_data[key] = {
						'total_liter': data['ack_liter'],
						'total_kg': data['ack_kg'],
						'total_fat': data['ack_fat'],
						'total_snf': data['ack_snf'],
						'total_kg_fat': data['ack_kg_fat'],
						'total_kg_snf': data['ack_kg_snf'],
						'count': 1,
						'date': data['date'],
						'shift': data['shift'],
						'dcs': data['dcs']
					}
				else:
					dcs_data[key]['total_liter'] += data['ack_liter']
					dcs_data[key]['total_kg'] += data['ack_kg']
					dcs_data[key]['total_fat'] += data['ack_fat']
					dcs_data[key]['total_snf'] += data['ack_snf']
					dcs_data[key]['total_kg_fat'] += data['ack_kg_fat']
					dcs_data[key]['total_kg_snf'] += data['ack_kg_snf']
					dcs_data[key]['count'] += 1
					
		total_qty_in_liter, total_qty_in_kg, fat, snf, kg_fat, kg_snf = 0, 0, 0, 0, 0, 0
		self.milk_received_from_dcs.clear()
		for key, values in dcs_data.items():
			count = values['count']
			total_qty_in_liter += values['total_liter']
			total_qty_in_kg += values['total_kg']
			fat += values['total_fat'] / count
			snf += values['total_snf'] / count
			# kg_fat += values['total_kg_fat']
			# kg_snf += values['total_kg_snf']
			self.append('milk_received_from_dcs', {
				'date': values['date'],
				'shift': values['shift'],
				'dcs': values['dcs'],
				'qty_in_liter': values['total_liter'],
				'qty_in_kg': values['total_kg'],
				'fat': values['total_fat'] / count,
				'snf': values['total_snf'] / count,
				'kg_fat': values['total_kg_fat'],
				'kg_snf': values['total_kg_snf'],
			})
		div = len(self.milk_received_from_dcs)
		if div > 0:
			fat = fat/div
			snf =  snf/div
			self.total_qty_in_liter, self.total_qty_in_kg, self.fat, self.snf, self.kg_fat, self.kg_snf = total_qty_in_liter, total_qty_in_kg, fat, snf, (total_qty_in_kg*fat)/100, (total_qty_in_kg*snf)/100

	@frappe.whitelist()
	def get_weight(self):
		weight = None
		item = self.get_item()
		if item:
			weight = frappe.db.get_value("Item", {"name": item}, "weight_per_unit")
		
		return weight

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

	@frappe.whitelist()
	def get_linked_stock_entries(self):
		stock_entries = frappe.get_all("Stock Entry",filters={"custom_tanker_inward": self.name, "docstatus": 1},fields=["name"], pluck='name')
		return len(stock_entries)

	@frappe.whitelist()
	def get_sales_summary(self):
		if self.si_qty_in_liter and self.sr_qty_in_liter:
			total_qty_in_liter = round(self.total_qty_in_liter, 3)
			total_qty_in_kg = round(self.total_qty_in_kg, 3)
			fat = round(self.fat, 3)
			snf = round(self.snf, 3)
			kg_fat = round(self.kg_fat, 3)
			kg_snf = round(self.kg_snf, 3)

			si_qty_in_liter = round(self.si_qty_in_liter, 3)
			si_qty_in_kg = round(self.si_qty_in_kg, 3)
			si_fat = round(self.si_fat, 3)
			si_snf = round(self.si_snf, 3)
			si_kg_fat = round(self.si_kg_fat, 3)
			si_kg_snf = round(self.si_kg_snf, 3)

			sr_qty_in_liter = round(self.sr_qty_in_liter, 3)
			sr_qty_in_kg = round(self.sr_qty_in_kg, 3)
			sr_fat = round(self.sr_fat, 3)
			sr_snf = round(self.sr_snf, 3)
			sr_kg_fat = round(self.sr_kg_fat, 3)
			sr_kg_snf = round(self.sr_kg_snf, 3)

			# Derived calculations with already rounded values
			total_sale_qty_ltr = round(si_qty_in_liter - sr_qty_in_liter, 3)
			total_sale_qty_kg = round(si_qty_in_kg - sr_qty_in_kg, 3)
			total_sale_fat = round(((si_kg_fat - sr_kg_fat) / total_sale_qty_kg) * 100, 3) if total_sale_qty_kg else 0
			total_sale_snf = round(((si_kg_snf - sr_kg_snf) / total_sale_qty_kg) * 100, 3) if total_sale_qty_kg else 0
			total_sale_kg_fat = round(si_kg_fat - sr_kg_fat, 3)
			total_sale_kg_snf = round(si_kg_snf - sr_kg_snf, 3)

			dcs_bal_qty_ltr = round(total_qty_in_liter - total_sale_qty_ltr, 3)
			dcs_bal_qty_kg = round(total_qty_in_kg - total_sale_qty_kg, 3)
			dcs_bal_kg_fat = round(kg_fat - total_sale_kg_fat, 3)
			dcs_bal_kg_snf = round(kg_snf - total_sale_kg_snf, 3)
			dcs_bal_fat = round((dcs_bal_kg_fat / dcs_bal_qty_kg) * 100, 3) if dcs_bal_qty_kg else 0
			dcs_bal_snf = round((dcs_bal_kg_snf / dcs_bal_qty_kg) * 100, 3) if dcs_bal_qty_kg else 0

			self.milk_sales_summary = f"""
				<table style="width:60%; border-collapse: collapse; text-align:center; font-size:13px; margin:-35px 0;">
					<thead>
						<tr style="background-color:#f9f9f9;">
							<th style="border:1px solid #ddd; padding:4px;">Description</th>
							<th style="border:1px solid #ddd; padding:4px;">Qty (Ltr)</th>
							<th style="border:1px solid #ddd; padding:4px;">Qty (Kg)</th>
							<th style="border:1px solid #ddd; padding:4px;">FAT</th>
							<th style="border:1px solid #ddd; padding:4px;">SNF</th>
							<th style="border:1px solid #ddd; padding:4px;">KG FAT</th>
							<th style="border:1px solid #ddd; padding:4px;">KG SNF</th>
						</tr>
					</thead>
					<tbody>
						<tr>
							<td style="border:1px solid #ddd; padding:4px;"><b>DCS COLLECTION MILK</b></td>
							<td style="border:1px solid #ddd; padding:4px;">{total_qty_in_liter}</td>
							<td style="border:1px solid #ddd; padding:4px;">{total_qty_in_kg}</td>
							<td style="border:1px solid #ddd; padding:4px;">{fat}</td>
							<td style="border:1px solid #ddd; padding:4px;">{snf}</td>
							<td style="border:1px solid #ddd; padding:4px;">{kg_fat}</td>
							<td style="border:1px solid #ddd; padding:4px;">{kg_snf}</td>
						</tr>
						<tr>
							<td style="border:1px solid #ddd; padding:4px;"><b>GIVEN TO SALE WAREHOUSE</b></td>
							<td style="border:1px solid #ddd; padding:4px;">{si_qty_in_liter}</td>
							<td style="border:1px solid #ddd; padding:4px;">{si_qty_in_kg}</td>
							<td style="border:1px solid #ddd; padding:4px;">{si_fat}</td>
							<td style="border:1px solid #ddd; padding:4px;">{si_snf}</td>
							<td style="border:1px solid #ddd; padding:4px;">{si_kg_fat}</td>
							<td style="border:1px solid #ddd; padding:4px;">{si_kg_snf}</td>
						</tr>
						<tr>
							<td style="border:1px solid #ddd; padding:4px;"><b>RETURN MILK IN SALE BALANCE</b></td>
							<td style="border:1px solid #ddd; padding:4px;">{sr_qty_in_liter}</td>
							<td style="border:1px solid #ddd; padding:4px;">{sr_qty_in_kg}</td>
							<td style="border:1px solid #ddd; padding:4px;">{sr_fat}</td>
							<td style="border:1px solid #ddd; padding:4px;">{sr_snf}</td>
							<td style="border:1px solid #ddd; padding:4px;">{sr_kg_fat}</td>
							<td style="border:1px solid #ddd; padding:4px;">{sr_kg_snf}</td>
						</tr>
						<tr>
							<td style="border:1px solid #ddd; padding:4px;"><b>TOTAL SALE WAREHOUSE TRANSFER</b></td>
							<td style="border:1px solid #ddd; padding:4px;">{total_sale_qty_ltr}</td>
							<td style="border:1px solid #ddd; padding:4px;">{total_sale_qty_kg}</td>
							<td style="border:1px solid #ddd; padding:4px;">{total_sale_fat}</td>
							<td style="border:1px solid #ddd; padding:4px;">{total_sale_snf}</td>
							<td style="border:1px solid #ddd; padding:4px;">{total_sale_kg_fat}</td>
							<td style="border:1px solid #ddd; padding:4px;">{total_sale_kg_snf}</td>
						</tr>
						<tr>
							<td style="border:1px solid #ddd; padding:4px;"><b>DCS COLLECTION MILK BALANCE</b></td>
							<td style="border:1px solid #ddd; padding:4px;">{dcs_bal_qty_ltr}</td>
							<td style="border:1px solid #ddd; padding:4px;">{dcs_bal_qty_kg}</td>
							<td style="border:1px solid #ddd; padding:4px;">{dcs_bal_fat}</td>
							<td style="border:1px solid #ddd; padding:4px;">{dcs_bal_snf}</td>
							<td style="border:1px solid #ddd; padding:4px;">{dcs_bal_kg_fat}</td>
							<td style="border:1px solid #ddd; padding:4px;">{dcs_bal_kg_snf}</td>
						</tr>
					</tbody>
				</table>
			"""

	# def before_save(self):
	# 	# for row in self.milk_received_from_dcs:
	# 	# 	# frappe.throw(str(row.qty_in_liter))
	# 	# 	total = row.qty_in_liter - self.si_qty_in_liter + self.sr_qty_in_liter
	# 	# for d in self.milk_received_from_tanker:
	# 	# 	data = total - d.qty_in_kg
	# 	# for i in self.difference_of_dcs_and_tanker_milk_received:
	# 	# 	i.qty_in_liter = data
	# 	# 		# frappe.throw(str(data))

	# 	if self.si_qty_in_liter < self.sr_qty_in_liter:
	# 		frappe.throw(f"SR Qty In Liter Can Not Greater Than SI Qty in Liter")

	# 	dcs_row = self.milk_received_from_dcs[0] if self.milk_received_from_dcs else None
	# 	tanker_row = self.milk_received_from_tanker[0] if self.milk_received_from_tanker else None
	
	# 	total_qty = flt(dcs_row.qty_in_liter) - flt(self.si_qty_in_liter) + flt(self.sr_qty_in_liter) - flt(tanker_row.qty_in_liter)
	# 	qty_data = round(flt(total_qty), 3)

	# 	total_qty_in_kg = flt(dcs_row.qty_in_kg) + self.si_qty_in_kg + self.sr_qty_in_kg + tanker_row.qty_in_kg / 4
	# 	qty_in_kg_data = round(flt(total_qty_in_kg), 3)
		

	# 	diff_row = self.append("difference_of_dcs_and_tanker_milk_received", {})
	# 	diff_row.dcs = self.sr_dcs
	# 	diff_row.qty_in_kg = qty_in_kg_data
	# 	diff_row.qty_in_liter = qty_data
	# 	diff_row.fat = 5
	# 	diff_row.snf = 5
	# 	# diff_row.qty_in_liter = flt(total)
	# 	# frappe.throw(str(total))
