// Copyright (c) 2025, BDF and contributors
// For license information, please see license.txt

// frappe.query_reports["BMC Wise Milk Collection"] = {
// 	"filters": [
// 		{"label": "From Date", "fieldname": "from_date", "fieldtype": "Date", "reqd": 1},
// 		{"label": "To Date", "fieldname": "to_date", "fieldtype": "Date", "reqd": 1},
// 		{"label": "Shift", "fieldname": "shift", "fieldtype": "Select", "options": "\nMorning\nEvening"},
// 		{"label": "DCS", "fieldname": "dcs", "fieldtype": "MultiSelectList", "options":"Warehouse",get_data: function(txt) {
// 			return frappe.db.get_link_options("Warehouse", txt);
// 		}},
// 		{"label": "Farmer", "fieldname": "member", "fieldtype": "MultiSelectList", "options":"Supplier",get_data: function(txt) {
// 			return frappe.db.get_link_options("Supplier", txt);
// 		}}
// 	]
// };

frappe.query_reports["BMC Wise Milk Collection"] = {
	"filters": [
		{"label": "From Date", "fieldname": "from_date", "fieldtype": "Date", "reqd": 1},
		{"label": "To Date", "fieldname": "to_date", "fieldtype": "Date", "reqd": 1},
		{"label": "Shift", "fieldname": "shift", "fieldtype": "Select", "options": "\nMorning\nEvening"},
		{"label": "DCS", "fieldname": "dcs", "fieldtype": "MultiSelectList", "options": "Warehouse", get_data: function(txt) {
			return frappe.db.get_link_options("Warehouse", txt);
		}},
		{"label": "Farmer", "fieldname": "member", "fieldtype": "MultiSelectList", "options": "Supplier", get_data: function(txt) {
			return frappe.db.get_link_options("Supplier", txt);
		}},
		{"label": "Member Group", "fieldname": "member_group", "fieldtype": "MultiSelectList", "options": "Supplier Group", get_data: function(txt) {
			return frappe.db.get_link_options("Supplier Group", txt);
		}},
		{"label": "Show DCS Total", "fieldname": "dcstotal", "fieldtype": "Check", "default": 0} // New checkbox filter
	]
};
