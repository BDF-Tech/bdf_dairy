import frappe
from frappe.model.document import Document
from frappe.utils import flt

# All quantities are calculated in KG. Litre fields are display only: litre = kg / KG_PER_LITRE
KG_PER_LITRE = 1.03


def kg_to_litre(kg):
	return flt(kg) / KG_PER_LITRE


class TankerInward(Document):
	def before_submit(self):
		diff_qty = sum(flt(diff.qty_in_kg) for diff in self.difference_of_dcs_and_tanker_milk_received)

		if flt(self.si_qty_in_kg) > 0 and not self.sales_item:
			frappe.throw("Sales Item is Mandatory")

		if diff_qty > 0 and not self.excess_warehouse:
			frappe.throw("Difference is Posotive. So Excess Warehouse Is Mandatory")
		if diff_qty < 0 and not self.loss_warehouse:
			frappe.throw("Difference is Negative. So Loss Warehouse Is Mandatory")

		self.material_transfer_from_dcs_to_tanker()

		if flt(self.si_qty_in_kg) > 0:
			self.material_transfer_from_tanker_to_sales()
		if flt(self.sr_qty_in_kg) > 0:
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
				"uom": "Kg",
				"conversion_factor": 0.9709,
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
				"uom": "Kg",
				"conversion_factor": 0.9709,
				"t_warehouse": self.excess_warehouse
			}],
			user_remark = self.vehicle_number
		)

	@frappe.whitelist()
	def material_transfer_from_dcs_to_tanker(self):
		items = []
		item_code = self.get_item()

    # -------------------------
    # 1. DCS (keep as-is)
    # -------------------------
		for itm in self.get('milk_received_from_dcs'):
			items.append({
				"item_code": item_code,
				"qty": itm.qty_in_kg,
				"uom": "Kg",
				"conversion_factor": 0.9709,
				"s_warehouse": itm.dcs,
				"t_warehouse": self.tanker_warehouse
			})

    # -------------------------
    # 2. CP Tanker (AGGREGATED)
    # -------------------------
		total_cp_qty = sum(
        (itm.qty_in_kg or 0)
        for itm in self.get('milk_received_from_cp_tanker')
    )

		if total_cp_qty > 0:
			items.append({
				"item_code": item_code,
				"qty": total_cp_qty,
				"uom": "Kg",
				"conversion_factor": 0.9709,
				"s_warehouse": self.dcs,
				"t_warehouse": self.tanker_warehouse
			})

    # -------------------------
    # 3. Create Stock Entry
    # -------------------------
		if items:
			self.create_stock_entry(
            stock_entry_type="Material Transfer",
            items=items
        )
	@frappe.whitelist()
	def material_transfer_from_tanker_to_plant(self, diff_qty=0):
		item_code = self.get_item()

		total_tanker_qty = sum(
        (itm.qty_in_kg or 0)
        for itm in self.get('milk_received_from_tanker')
    )

    # 🔥 YOUR EXACT REQUIREMENT
		plant_qty = total_tanker_qty

		if diff_qty > 0:
			plant_qty -= diff_qty  # subtract only when excess

		if plant_qty <= 0:
			frappe.throw("Invalid tanker to plant quantity")

		self.create_stock_entry(
			stock_entry_type="Material Transfer",
			items=[{
				"item_code": item_code,
				"qty": plant_qty,
				"uom": "Kg",
				"conversion_factor": 0.9709,
				"s_warehouse": self.tanker_warehouse,
				"t_warehouse": self.plant_warehouse
			}]
		)

	@frappe.whitelist()
	def material_transfer_from_tanker_to_sales(self):
		liter_qty = round(self.si_qty_in_kg * 0.9709, 3)
		items = [
			{
				"item_code": self.get_item(),
				"qty": self.si_qty_in_kg,
				"uom": "Kg",
				"conversion_factor": 0.9709,
				"s_warehouse": self.tanker_warehouse,
			},
			{
				"item_code": self.sales_item,
				"qty": liter_qty,
				"uom": "Litre",
				"conversion_factor": 1,
				"t_warehouse": self.si_dcs
			}
		]
		self.create_stock_entry(stock_entry_type="Repack", items=items)

	@frappe.whitelist()
	def material_transfer_from_sales_to_tanker(self):
		liter_qty = round(self.sr_qty_in_kg * 0.9709, 3)
		items = [
			{
				"item_code": self.sales_item,
				"qty": liter_qty,
				"uom": "Litre",
				"conversion_factor": 1,
				"s_warehouse": self.si_dcs,
			},
			{
				"item_code": self.get_item(),
				"qty": self.sr_qty_in_kg,
				"uom": "Kg",
				"conversion_factor": 0.9709,
				"t_warehouse": self.tanker_warehouse
			}
		]
		self.create_stock_entry(stock_entry_type="Repack", items=items)

	@frappe.whitelist()
	def material_transfer_from_tanker_to_loss(self, qty):
		items = []
		items.append({
			"item_code": self.get_item(),
			"qty": qty,
			"uom": "Kg",
			"conversion_factor": 0.9709,
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
			"uom": "Kg",
			"conversion_factor": 0.9709,
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
		return sum(flt(diff.qty_in_kg) for diff in self.difference_of_dcs_and_tanker_milk_received if flt(diff.qty_in_kg) > 0)

	def validate(self):
		self.clear_cp_tanker_rows_for_cp_collection()
		self.validate_cp_tanker_inwards()

	def clear_cp_tanker_rows_for_cp_collection(self):
		# A CP collection inward itself never receives milk from other CP tankers
		if self.dcs and frappe.get_cached_value("Warehouse", self.dcs, "custom_cp_warehouse"):
			self.cp_collection = 1
			self.milk_received_from_cp_tanker = []

	def validate_cp_tanker_inwards(self):
		tanker_ids = {row.tanker_id for row in self.milk_received_from_cp_tanker if row.tanker_id}
		if not tanker_ids:
			return

		if self.name in tanker_ids:
			frappe.throw(f"Tanker Inward {self.name} can not be added as its own CP Tanker Inward.")

		already_used = frappe.get_all(
			"Other Inward",
			filters={
				"parenttype": "Tanker Inward",
				"parentfield": "milk_received_from_cp_tanker",
				"tanker_id": ["in", list(tanker_ids)],
				"parent": ["!=", self.name],
				"docstatus": 1,
			},
			fields=["tanker_id", "parent"],
		)
		if already_used:
			used = ", ".join(sorted({f"{d.tanker_id} (in {d.parent})" for d in already_used}))
			frappe.throw(f"CP Tanker Inward already used in another submitted Tanker Inward: {used}")

	def before_save(self):
		if flt(self.si_qty_in_kg) < flt(self.sr_qty_in_kg):
			frappe.throw(f"Return Qty Can Not Greater Than Sales Qty.")

		self.set_litre_from_kg()
		self.calculate_cp_totals()
		self.calculate_dcs_and_cp_totals()
		self.set_difference_row()

	def set_litre_from_kg(self):
		for table, litre_field in (
			("milk_received_from_dcs", "qty_in_liter"),
			("milk_received_from_tanker", "qty_in_liter"),
			("milk_received_from_cp_tanker", "qty_in_litre"),
		):
			for row in self.get(table):
				row.set(litre_field, kg_to_litre(row.qty_in_kg))

		self.si_qty_in_liter = kg_to_litre(self.si_qty_in_kg)
		self.sr_qty_in_liter = kg_to_litre(self.sr_qty_in_kg)

	def calculate_cp_totals(self):
		rows = self.milk_received_from_cp_tanker
		self.total_qty_in_kg1 = sum(flt(row.qty_in_kg) for row in rows)
		self.total_qty_in_litre1 = kg_to_litre(self.total_qty_in_kg1)
		self.kg_fat1 = sum(flt(row.kg_fat) for row in rows)
		self.kg_snf1 = sum(flt(row.kg_snf) for row in rows)
		self.fat1 = (self.kg_fat1 / self.total_qty_in_kg1) * 100 if self.total_qty_in_kg1 else 0
		self.snf1 = (self.kg_snf1 / self.total_qty_in_kg1) * 100 if self.total_qty_in_kg1 else 0

	def set_difference_row(self):
		# Tanker received minus (DCS + CP collection - depot sales + sales return), all in KG
		expected_kg = flt(self.total_qty_in_kg) - flt(self.si_qty_in_kg) + flt(self.sr_qty_in_kg)
		expected_kg_fat = flt(self.kg_fat) - flt(self.si_kg_fat) + flt(self.sr_kg_fat)
		expected_kg_snf = flt(self.kg_snf) - flt(self.si_kg_snf) + flt(self.sr_kg_snf)
		# FAT/SNF % of the expected milk comes from its KG FAT/SNF; percentages can not be added or subtracted
		expected_fat = (expected_kg_fat / expected_kg) * 100 if expected_kg else 0
		expected_snf = (expected_kg_snf / expected_kg) * 100 if expected_kg else 0

		tanker_rows = self.milk_received_from_tanker
		tanker_kg = sum(flt(m.qty_in_kg) for m in tanker_rows)
		if tanker_kg:
			tanker_fat = sum(flt(m.fat) * flt(m.qty_in_kg) for m in tanker_rows) / tanker_kg
			tanker_snf = sum(flt(m.snf) * flt(m.qty_in_kg) for m in tanker_rows) / tanker_kg
		else:
			tanker_fat = tanker_snf = 0

		qty_kg = tanker_kg - expected_kg

		self.difference_of_dcs_and_tanker_milk_received.clear()
		diff_row = self.append("difference_of_dcs_and_tanker_milk_received", {})
		diff_row.dcs = self.dcs
		diff_row.qty_in_kg = qty_kg
		diff_row.qty_in_liter = kg_to_litre(qty_kg)
		diff_row.fat = tanker_fat - expected_fat
		diff_row.snf = tanker_snf - expected_snf
		diff_row.kg_fat = sum(flt(m.kg_fat) for m in tanker_rows) - expected_kg_fat
		diff_row.kg_snf = sum(flt(m.kg_snf) for m in tanker_rows) - expected_kg_snf

	def calculate_dcs_and_cp_totals(self):
		dcs_kg = sum(flt(row.qty_in_kg) for row in self.milk_received_from_dcs)
		dcs_kg_fat = sum(flt(row.kg_fat) for row in self.milk_received_from_dcs)
		dcs_kg_snf = sum(flt(row.kg_snf) for row in self.milk_received_from_dcs)

		final_kg = dcs_kg + flt(self.total_qty_in_kg1)
		final_kg_fat = dcs_kg_fat + flt(self.kg_fat1)
		final_kg_snf = dcs_kg_snf + flt(self.kg_snf1)

		self.total_qty_in_kg = final_kg
		self.total_qty_in_liter = kg_to_litre(final_kg)
		self.kg_fat = final_kg_fat
		self.kg_snf = final_kg_snf
		self.fat = (final_kg_fat / final_kg) * 100 if final_kg else 0
		self.snf = (final_kg_snf / final_kg) * 100 if final_kg else 0

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
					SUM(volume) / 1.03 as ack_liter,
					SUM(volume) as ack_kg,
					((SUM(fat_kg) / SUM(volume)) * 100) as ack_fat,
					((SUM(snf_kg) / SUM(volume)) * 100) as ack_snf,
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
		self.calculate_dcs_and_cp_totals()

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
		if self.si_qty_in_kg and self.sr_qty_in_kg:
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

@frappe.whitelist()
def get_cp_tanker_inwards(from_date, to_date, bmc_warehouse, milk_type, current_name=None, cp_warehouses=None):
	"""Submitted CP Tanker Inwards that delivered milk to `bmc_warehouse` in the date range
	and are not yet used in another submitted Tanker Inward. One row per Milk Received From Tanker row."""
	frappe.has_permission("Tanker Inward", "read", throw=True)

	cp_filters = {"custom_cp_warehouse": 1}
	cp_warehouses = frappe.parse_json(cp_warehouses) if cp_warehouses else []
	if cp_warehouses:
		cp_filters["name"] = ["in", cp_warehouses]
	cp_warehouses = frappe.get_all("Warehouse", filters=cp_filters, pluck="name")
	if not cp_warehouses:
		return []

	return frappe.db.sql(
		"""
		SELECT
			ti.name AS tanker_id,
			ti.dcs,
			ti.from_date,
			ti.to_date,
			ti.from_shift,
			ti.to_shift,
			mrt.qty_in_liter AS qty_in_litre,
			mrt.qty_in_kg,
			mrt.fat,
			mrt.snf,
			mrt.kg_fat,
			mrt.kg_snf
		FROM `tabTanker Inward` ti
		INNER JOIN `tabMilk Received From Tanker` mrt
			ON mrt.parent = ti.name
			AND mrt.parenttype = 'Tanker Inward'
			AND mrt.parentfield = 'milk_received_from_tanker'
		WHERE
			ti.docstatus = 1
			AND ti.dcs IN %(cp_warehouses)s
			AND ti.plant_warehouse = %(bmc_warehouse)s
			AND ti.milk_type = %(milk_type)s
			AND ti.from_date <= %(to_date)s
			AND ti.to_date >= %(from_date)s
			AND ti.name != %(current_name)s
			AND NOT EXISTS (
				SELECT 1 FROM `tabOther Inward` oi
				WHERE oi.tanker_id = ti.name
					AND oi.parenttype = 'Tanker Inward'
					AND oi.parentfield = 'milk_received_from_cp_tanker'
					AND oi.docstatus = 1
					AND oi.parent != %(current_name)s
			)
		ORDER BY ti.from_date, ti.dcs, ti.name, mrt.idx
		""",
		{
			"cp_warehouses": cp_warehouses,
			"bmc_warehouse": bmc_warehouse,
			"milk_type": milk_type,
			"from_date": from_date,
			"to_date": to_date,
			"current_name": current_name or "",
		},
		as_dict=True,
	)
