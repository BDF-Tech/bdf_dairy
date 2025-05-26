# Copyright (c) 2025, BDF and contributors
# For license information, please see license.txt

import json
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

		raw_data  = milk_data_response.get("Data")
		try:
			milk_data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
		except json.JSONDecodeError:
			frappe.throw("Milk data in 'Data' field is not valid JSON.")

		# Sanity check
		if not milk_data or not isinstance(milk_data, list):
			frappe.throw("No valid milk data found or data is not a list.")

		for entry in milk_data:
			required_keys = ["Member_Code", "Milk_Type", "Shift", "Transaction_Date", "Qty_Ltr", "Fat", "Snf", "CLR"]
			for key in required_keys:
				if key not in entry:
					frappe.throw(f"Missing key in milk data: {key}")
			
			supplier = frappe.db.exists("Supplier", {'custom_member_code': float(entry.get("Member_Code"))})
			if not supplier:
				frappe.throw(f"Member Code Mapping is Missing Or Supplier Is Missing For {entry.get('Member_Code')}")

			milk_doc = frappe.get_doc({
				"doctype": "Milk Entry",
				"dcs_id": self.warehouse,
				"member": supplier,
				"milk_type": "Cow" if entry.get("Milk_Type") == "C" else "Buffalo" if entry.get("Milk_Type") == "B" else "Mix",
				"shift": "Morning" if entry.get("Shift") == "M" else "Evening",
				"date": getdate(entry.get("Transaction_Date")),
				"volume": entry.get("Qty_Ltr"),
				"fat": entry.get("Fat"),
				"snf": entry.get("Snf"),
				"clr": entry.get("CLR")
			})

			# Save to DB
			milk_doc.insert(ignore_permissions=True)
			milk_doc.save(ignore_permissions=True)
