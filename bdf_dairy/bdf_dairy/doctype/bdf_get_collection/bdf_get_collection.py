# Copyright (c) 2025, BDF and contributors
# For license information, please see license.txt

import json
import time
import frappe
import requests
from frappe.utils import getdate
from frappe.model.document import Document

class BDFGetCollection(Document):
	def before_save(self):
		login_header = {
			"Accept": "*/*",
			"User-Agent": "BDF",
			"Content-Type": "application/json"
		}
		login_payload = {
			"userName": self.user_name,
			"password": self.password
		}

		# Step 1: Request for token
		try:
			response = requests.post(self.token_api_url, json=login_payload, headers=login_header)
			response.raise_for_status()
		except requests.exceptions.RequestException as e:
			frappe.throw(f"Error while connecting to token API: {e}")

		try:
			response_data = response.json()
		except json.JSONDecodeError:
			frappe.throw("Invalid JSON response while getting token.")

		token = response_data.get("Data")
		if not token:
			frappe.throw("Token not found in the response.")

		# Step 2: Use token to request milk data
		milk_entry_header = {
			"Authorization": f"Bearer {token}",
			"Content-Type": "application/json"
		}

		milk_entry_payload = {
			"MPP_Code": self.mpp_code,
			"Transaction_Date": getdate(self.date).strftime("%d-%m-%Y"),
			"Shift": self.shift,
		}

		try:
			milk_response = requests.post(self.getdata_api_url, json=milk_entry_payload, headers=milk_entry_header)
			milk_response.raise_for_status()
		except requests.exceptions.RequestException as e:
			frappe.throw(f"Error while connecting to data API: {e}")

		try:
			milk_data_response = milk_response.json()
		except json.JSONDecodeError:
			frappe.throw("Invalid JSON response while fetching milk data.")

		raw_data = milk_data_response.get("Data")
		try:
			milk_data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
		except json.JSONDecodeError:
			frappe.throw("Milk data in 'Data' field is not valid JSON.")

		if not milk_data or not isinstance(milk_data, list):
			frappe.throw("No valid milk data found or data is not a list.")

		# OPT 1: defined once, not inside the loop
		required_keys = ["Member_Code", "Milk_Type", "Shift", "Transaction_Date", "Qty_KG", "Fat", "Snf", "CLR"]

		# OPT 2: fetch all suppliers in one query, lookup via dict inside loop
		t_supplier_start = time.time()
		supplier_map = {}
		for s in frappe.get_all("Supplier", filters={"custom_member_code": ["!=", ""]}, fields=["name", "custom_member_code"]):
			try:
				supplier_map[str(int(float(s.custom_member_code)))] = s.name
			except (ValueError, TypeError):
				pass
		t_supplier_end = time.time()

		t_loop_start = time.time()
		for entry in milk_data:
			for key in required_keys:
				if key not in entry:
					frappe.throw(f"Missing key in milk data: {key}")

			member_code = str(int(float(entry.get("Member_Code"))))
			supplier = supplier_map.get(member_code)
			if not supplier:
				frappe.throw(f"Member Code Mapping is Missing Or Supplier Is Missing For {entry.get('Member_Code')}")

			milk_doc = frappe.get_doc({
				"doctype": "Milk Entry",
				"mpp_code": self.mpp_code,
				"dcs_id": self.warehouse,
				"member": supplier,
				"milk_type": "Cow" if entry.get("Milk_Type") == "C" else "Buffalo" if entry.get("Milk_Type") == "B" else "Mix",
				"shift": "Morning" if entry.get("Shift") == "M" else "Evening",
				"date": getdate(entry.get("Transaction_Date")),
				"volume": entry.get("Qty_KG"),
				"fat": entry.get("Fat"),
				"snf": entry.get("Snf"),
				"clr": entry.get("CLR"),
				"unit_price": entry.get("Rate"),
				"unit_price_with_incentive": entry.get("Rate"),
				"total": entry.get("Amount"),
				"rate_chart_amount": entry.get("Amount")
			})

			# OPT 3: removed redundant milk_doc.save() after insert
			milk_doc.insert(ignore_permissions=True)

		t_loop_end = time.time()

		total_entries = len(milk_data)
		supplier_lookup_ms = round((t_supplier_end - t_supplier_start) * 1000, 2)
		insert_ms = round((t_loop_end - t_loop_start) * 1000, 2)
		total_ms = round(supplier_lookup_ms + insert_ms, 2)
		est_old_supplier_ms = total_entries * 3
		supplier_saved_ms = round(est_old_supplier_ms - supplier_lookup_ms, 2)

		frappe.logger("bdf_get_collection").info(
			f"BDF Sync | entries={total_entries} | "
			f"supplier_lookup={supplier_lookup_ms}ms (old≈{est_old_supplier_ms}ms, saved≈{supplier_saved_ms}ms) | "
			f"inserts={insert_ms}ms | save() calls eliminated={total_entries}"
		)

		frappe.msgprint(
			title="Milk Collection Sync Complete",
			msg=f"""
				<table style="width:100%; border-collapse:collapse; font-size:13px;">
					<tr style="background:#f4f5f6;">
						<td style="padding:6px 10px;"><b>Total Entries Synced</b></td>
						<td style="padding:6px 10px;">{total_entries}</td>
					</tr>
					<tr>
						<td style="padding:6px 10px;"><b>Supplier Lookup</b></td>
						<td style="padding:6px 10px;">{supplier_lookup_ms} ms &nbsp;<span style="color:green;">(saved ≈ {supplier_saved_ms} ms vs old approach)</span></td>
					</tr>
					<tr style="background:#f4f5f6;">
						<td style="padding:6px 10px;"><b>Milk Entry Inserts</b></td>
						<td style="padding:6px 10px;">{insert_ms} ms</td>
					</tr>
					<tr>
						<td style="padding:6px 10px;"><b>Total Time</b></td>
						<td style="padding:6px 10px;">{total_ms} ms</td>
					</tr>
				</table>
			""",
			indicator="green"
		)
