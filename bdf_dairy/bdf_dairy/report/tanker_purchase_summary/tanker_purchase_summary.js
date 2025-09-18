// Copyright (c) 2025, BDF and contributors
// For license information, please see license.txt

frappe.query_reports["Tanker Purchase Summary"] = {
    "filters": [
		{
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            default: frappe.datetime.add_days(frappe.datetime.get_today(), -7),
			reqd: 1
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
			reqd: 1
        },
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            reqd: 1
        },
        {
            fieldname: "shift",
            label: __("Shift"),
            fieldtype: "Select",
            options: ["", "Morning", "Evening"]
        },
        {
            fieldname: "supplier",
            label: __("Supplier"),
            fieldtype: "MultiSelectList",
            get_data: function(txt) {
                return frappe.db.get_link_options('Supplier', txt);
            }
        },
        {
            fieldname: "dcs",
            label: __("DCS"),
            fieldtype: "MultiSelectList",
            get_data: function(txt) {
                return frappe.db.get_link_options('Warehouse', txt, {
                    is_dcs: 1,
                    disabled: 0
                });
            }
        }
    ]
};
