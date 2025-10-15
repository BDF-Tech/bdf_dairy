// Copyright (c) 2025, BDF and contributors
// For license information, please see license.txt

frappe.query_reports["Milk Standardization Consumption Report"] = {
	"filters": [
		{
			"fieldname": "name",
			"label": "Id",
			"fieldtype": "Link",
			"options": "Milk Standardization"
		},
		{
			"fieldname": "from_date",
			"label": "From Date",
			"fieldtype": "Date",
		},
		{
			"fieldname": "to_date",
			"label": "To Date",
			"fieldtype": "Date",
		},
		{
			"fieldname": "finished_item_name",
			"label": "Finished Item",
			"fieldtype": "Link",
			"options": "Item"
		},
	]
};
    