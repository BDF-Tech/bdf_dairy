# Copyright (c) 2025, BDF and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.model.document import Document


class FarmerBilling(Document):
	def autoname(self):
		self.name = f"{self.from_date}--{self.to_date}--{self.dcs}"

	def before_submit(self):
		self.create_purchase_invoice()

	@frappe.whitelist()
	def get_milk_entry_detail_data(self):
		self.farmer_billing_details.clear()
		milk_entries = frappe.get_all(
			"Milk Entry",
			filters={'date': ['between', [self.from_date, self.to_date]], 'dcs_id': self.dcs},
			fields=[
				'name', 'date', 'shift', 'member', 'member_name', 'milk_type',
				'fat', 'snf', 'volume', 'unit_price_with_incentive'
			]
		)
		
		for entry in milk_entries:
			purchase_receipt = frappe.db.exists("Purchase Receipt", {'milk_entry': entry['name']})
			
			self.append('farmer_billing_details', {
				'milk_entry_date': entry['date'],
				'milk_entry_shift': entry['shift'],
				'milk_entry': entry['name'],
				'milk_type': entry['milk_type'],
				'farmer': entry['member'],
				'farmer_name': entry['member_name'],
				'purchase_receipt': purchase_receipt,
				'fat_': entry['fat'],
				'snf_': entry['snf'],
				'qty': entry['volume'],
				'rate': entry['unit_price_with_incentive'],
				'amount': entry['volume'] * entry['unit_price_with_incentive'],
			})
		self.get_milk_entry_summary_data()

	def get_milk_entry_summary_data(self):
		self.farmer_billing_summary.clear()
		milk_entries = frappe.db.get_list(
			"Milk Entry",
			filters={'date': ['between', [self.from_date, self.to_date]],'dcs_id': self.dcs},
			fields=['member', 'member_name', 'SUM(volume) as total_volume', 'AVG(unit_price_with_incentive) as avg_rate'
			],
			group_by='member'
		)

		for entry in milk_entries:
			self.append('farmer_billing_summary', {
				'farmer': entry['member'],
				'farmer_name': entry['member_name'],
				'qty': entry['total_volume'],
				'amount': entry['total_volume'] * entry['avg_rate']
			})

	def create_purchase_invoice(self):
		milk_type = {'Cow': 'cow_pro', 'Buffalo': 'buf_pro', 'Mix': 'mix_pro'}
		
		for farmer_summary in self.farmer_billing_summary:
			farmer = farmer_summary.farmer
			purchase_inv = frappe.new_doc("Purchase Invoice")
			purchase_inv.supplier = farmer
			purchase_inv.posting_date = self.billing_date
			purchase_inv.custom_farmer_billing = self.name
			purchase_inv.company = self.company
			purchase_inv.custom_remark = farmer
			purchase_inv.cost_center = 'DCS-08Plant - BDF - BDF'

			entries = [entry for entry in self.farmer_billing_details if entry.farmer == farmer]

			for entry in entries:
				item_code = frappe.db.get_single_value("Dairy Settings", milk_type.get(entry.milk_type))
				stock_uom = frappe.get_value("Item", item_code, 'stock_uom')

				purchase_inv.append('items', {
					'item_code': item_code,
					'received_qty': entry.qty,
					'qty': entry.qty,
					'uom': stock_uom,
					'stock_uom': stock_uom,
					'rate': entry.rate,
					'warehouse': self.dcs,
					'purchase_receipt': entry.purchase_receipt,
					'fat': entry.fat_,
					'snf': entry.snf_,
					'milk_entry': entry.milk_entry,
				})
			purchase_inv.save()
			purchase_inv.submit()
			frappe.msgprint(f"Purchase Invoice {purchase_inv.name} created for {farmer}")
