import frappe
from frappe.model.document import Document

class TankerInward(Document):
	def before_submit(self):
		diff_qty = 0
		for diff in self.get('difference_of_dcs_and_tanker_milk_received', filters={'qty_in_liter': ['>', 0]}):
			diff_qty += diff.qty_in_liter
		for diff in self.get('difference_of_dcs_and_tanker_milk_received', filters={'qty_in_liter': ['<', 0]}):
			diff_qty += diff.qty_in_liter
		
		self.material_transfer_from_dcs_to_tanker()
		if diff_qty > 0:
			self.material_receipt_to_tanker(diff_qty)
		if diff_qty < 0:
			self.material_transfer_from_tanker_to_loss(abs(diff_qty))
		self.material_transfer_from_tanker_to_plant()

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
	def material_transfer_from_tanker_to_plant(self):
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
	def material_transfer_from_tanker_to_loss(self, qty):
		items = []
		for itm in self.get('milk_received_from_tanker'):
			items.append({
				"item_code": self.get_item(),
				"qty": qty,
				"s_warehouse": self.tanker_warehouse,
				"t_warehouse": self.loss_warehouse
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
		# stock_entry.insert()
		stock_entry.save()
		stock_entry.submit()
			# frappe.db.commit()

		# except frappe.ValidationError as e:
		# 	frappe.db.rollback()
		# 	frappe.throw(f"Validation Error: {e}")
		# except Exception as e:
		# 	frappe.db.rollback()
		# 	frappe.throw(f"Error: {e}")

	@frappe.whitelist()
	def get_material_receipt(self):
		diff_qty = 0
		for diff in self.get('difference_of_dcs_and_tanker_milk_received', filters={'qty_in_liter': ['>', 0]}):
			diff_qty += diff.qty_in_liter
		return diff_qty

	def before_save(self):
		self.difference_of_dcs_and_tanker_milk_received.clear()
		for m in self.milk_received_from_tanker:
			self.append('difference_of_dcs_and_tanker_milk_received', {
				'dcs': m.dcs,
				'qty_in_liter': m.qty_in_liter - self.total_qty_in_liter,
				'qty_in_kg': m.qty_in_kg - self.total_qty_in_kg,
				'fat': m.fat - self.fat,
				'snf': m.snf - self.snf,
				'kg_fat': m.kg_fat - self.kg_fat,
				'kg_snf': m.kg_snf - self.kg_snf,
			})

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
					AVG(fat) as ack_fat, 
					AVG(snf) as ack_snf,
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
			kg_fat += values['total_kg_fat']
			kg_snf += values['total_kg_snf']
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
			self.total_qty_in_liter, self.total_qty_in_kg, self.fat, self.snf, self.kg_fat, self.kg_snf = total_qty_in_liter, total_qty_in_kg, fat/div, snf/div, kg_fat, kg_snf

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