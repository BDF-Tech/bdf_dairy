# Copyright (c) 2025, BDF and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class FarmerBilling(Document):
	def autoname(self):
		pattern = f"{self.from_date}--{self.to_date}--{self.dcs}%"
		counter = frappe.db.count("Farmer Billing", filters={"name": ["like", pattern]})
		self.name = f"{self.from_date}--{self.to_date}--{self.dcs}--{counter + 1}"

	def before_submit(self):
		self.create_purchase_invoice()

	def before_save(self):
		self.get_running_total()

	def get_running_total(self):
		total_qty, total_amount = 0, 0
		for row in self.farmer_billing_summary:
			total_qty += row.qty
			total_amount += row.amount

		self.total_qty = total_qty
		self.average_rate = total_amount / total_qty
		self.total_amount = total_amount

	@frappe.whitelist()
	def get_milk_entry_detail_data(self):
		self.farmer_billing_details.clear()
		if not self.from_date:
			frappe.throw("From Date Is Missing.")
	
		if not self.no_of_date:
			frappe.throw("Number Of Days Is Missing.")

		if not self.dcs:
			frappe.throw("DCS Is Missing.")

		milk_entries = frappe.get_all(
			"Milk Entry",
			filters={
				'date': ['between', [self.from_date, self.to_date]],
				'dcs_id': self.dcs, 'docstatus': 1, 'status': ['!=', 'Billed']
			},
			fields=[
				'name', 'date', 'shift', 'member', 'member_name', 'milk_type',
				'fat', 'snf', 'volume', 'unit_price_with_incentive'
			],
			order_by='member_name ASC, date ASC, shift DESC'
		)

		if not milk_entries:
			frappe.throw("No Milk Entry Found.")

		entry_names = [entry['name'] for entry in milk_entries]
		receipt_map = frappe._dict({
			d.milk_entry: d.name for d in frappe.get_all(
				"Purchase Receipt",
				filters={'milk_entry': ['in', entry_names]},
				fields=['milk_entry', 'name']
			)
		})

		# Summary dictionary
		farmer_summary = {}

		for entry in milk_entries:
			volume = entry['volume'] or 0
			rate = entry['unit_price_with_incentive'] or 0
			amount = volume * rate
			member = entry['member']
			member_name = entry['member_name']

			# Append to child table
			self.append('farmer_billing_details', {
				'milk_entry_date': entry['date'],
				'milk_entry_shift': entry['shift'],
				'milk_entry': entry['name'],
				'milk_type': entry['milk_type'],
				'farmer': member,
				'farmer_name': member_name,
				'purchase_receipt': receipt_map.get(entry['name']),
				'fat_': entry['fat'],
				'snf_': entry['snf'],
				'qty': volume,
				'rate': rate,
				'amount': amount,
			})

			# Build the summary dict
			if member not in farmer_summary:
				farmer_summary[member] = {
					"member_name": member_name,
					"total_qty": 0,
					"total_amount": 0,
					"entry_count": 0
				}

			farmer_summary[member]["total_qty"] += volume
			farmer_summary[member]["total_amount"] += amount
			farmer_summary[member]["entry_count"] += 1

		# Prepare final list of dicts
		summary_list = []
		for member, data in farmer_summary.items():
			summary_list.append({
				'member': member,
				'member_name': data["member_name"],
				'qty': data["total_qty"],
				'amount': data["total_amount"]
			})

		for entry in summary_list:
			self.append('farmer_billing_summary', {
				'farmer': entry['member'],
				'farmer_name': entry['member_name'],
				'qty':  entry['qty'],
				'rate': entry['amount'] / entry['qty'],
				'amount':  entry['amount']
			})
		self.get_running_total()


	def create_purchase_invoice(self):
		milk_type = {'Cow': 'cow_pro', 'Buffalo': 'buf_pro', 'Mix': 'mix_pro'}
		milk_entry = []
		for farmer_summary in self.farmer_billing_summary:
			farmer = farmer_summary.farmer
			purchase_inv = frappe.new_doc("Purchase Invoice")
			purchase_inv.supplier = farmer
			purchase_inv.posting_date = self.billing_date
			purchase_inv.set_posting_time = 1
			purchase_inv.due_date = self.due_date
			purchase_inv.custom_farmer_billings = self.name
			purchase_inv.company = self.company
			purchase_inv.custom_remark = farmer
			purchase_inv.cost_center = self.cost_center

			entries = [entry for entry in self.farmer_billing_details if entry.farmer == farmer]

			for entry in entries:
				item_code = frappe.db.get_single_value("Dairy Settings", milk_type.get(entry.milk_type))
				stock_uom = frappe.get_value("Item", item_code, 'stock_uom')
				milk_entry.append(entry.milk_entry)
				purchase_inv.append('items', {
					'item_code': item_code,
					'received_qty': entry.qty,
					'qty': entry.qty,
					'uom': stock_uom,
					'stock_uom': stock_uom,
					'rate': entry.rate,
					'warehouse': self.dcs,
					'purchase_receipt': entry.purchase_receipt,
					'pr_detail': frappe.get_value("Purchase Receipt Item", {'parent':entry.purchase_receipt, "item_code": item_code}, 'name'),
					'fat': entry.fat_,
					'snf': entry.snf_,
					'milk_entry': entry.milk_entry,
				})
				# frappe.db.set_value("Purchase Receipt", entry.purchase_receipt, "status", "Completed")
				# frappe.db.set_value("Purchase Receipt", entry.purchase_receipt, "per_billed", "100")
			purchase_inv.save()
			purchase_inv.submit()
			frappe.msgprint(f"Purchase Invoice {purchase_inv.name} created for {farmer}")

		for entry in milk_entry:
			frappe.db.set_value("Milk Entry", entry, 'status', 'Billed')

	def on_cancel(self):
		purchase_invoices = frappe.get_list(
			"Purchase Invoice",
			filters={"custom_farmer_billings": self.name},
			pluck="name"
		)

		if not purchase_invoices:
			frappe.msgprint("No linked Purchase Invoices found.")
			return

		for pi_name in purchase_invoices:
			pi_doc = frappe.get_doc("Purchase Invoice", pi_name)
			if pi_doc.docstatus == 1:
				try:
					pi_doc.cancel()
					frappe.msgprint(f"Purchase Invoice {pi_name} has been cancelled.")
				except Exception as e:
					frappe.log_error(frappe.get_traceback(), f"Failed to cancel Purchase Invoice {pi_name}")
					frappe.throw(f"Error cancelling Purchase Invoice {pi_name}: {str(e)}")

