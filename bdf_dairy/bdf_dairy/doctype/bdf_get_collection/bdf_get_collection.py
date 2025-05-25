# Copyright (c) 2025, BDF and contributors
# For license information, please see license.txt

import json
import frappe
import requests
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
			"Transaction_Date": self.date,
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

		milk_data = milk_data_response.get("Data")
		if not milk_data or not isinstance(milk_data, dict):
			frappe.throw("No valid milk data found in the response.")

		# Optional: Validate required fields
		required_keys = ["Member_Code", "Milk_Type", "Shift", "Transaction_Date", "Qty_Ltr", "Fat", "Snf", "CLR"]
		for key in required_keys:
			if key not in milk_data:
				frappe.throw(f"Missing key in milk data: {key}")

		# Create new Milk Entry
		milk_doc = frappe.get_doc({
			"doctype": "Milk Entry",
			"dcs_id": milk_data,
			"member": milk_data["Member_Code"],
			"milk_type": "Cow" if milk_data["Milk_Type"] == "C" else "Buffalo" if milk_data["Milk_Type"] == "B" else "Mix",
			"shift": "Morning" if milk_data["Shift"] == "M" else "Evening",
			"date": milk_data["Transaction_Date"],
			"volume": milk_data["Qty_Ltr"],
			"fat": milk_data["Fat"],
			"snf": milk_data["Snf"],
			"clr": milk_data["CLR"]
		})
		milk_doc.insert(ignore_permissions=True)
		milk_doc.save(ignore_permissions=True)
