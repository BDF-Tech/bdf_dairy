// Copyright (c) 2024, BDF and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Tanker Inward Summary"] = {
	"filters": [
		{"label": "From Date", "fieldname": "from_date", "fieldtype": "Date", "reqd": 1},
		{"label": "To Date", "fieldname": "to_date", "fieldtype": "Date", "reqd": 1},
		{"label": "DCS", "fieldname": "dcs", "fieldtype": "MultiSelectList", "options":"Warehouse",get_data: function(txt) {
			return frappe.db.get_link_options("Warehouse", txt);
		}},
		{"label": "CP Colection", "fieldname": "cp_collection", "fieldtype": "Check", "default": 0},
	]
};
