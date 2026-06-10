frappe.query_reports["Department Report Sheet"] = {
    filters: [
        {
            fieldname: "report_type",
            label: __("Report Type"),
            fieldtype: "Select",
            options: "Daily\nWeekly\nMonthly",
            default: "Daily",
            on_change: function () {
                let summarized = frappe.query_report.get_filter_value("summarized_view");
                let val = frappe.query_report.get_filter_value("report_type");
                if (summarized) return;
                frappe.query_report.toggle_filter_display("month", val === "Monthly");
                frappe.query_report.refresh();
            }
        },
        {
            fieldname: "month",
            label: __("Month"),
            fieldtype: "Select",
            options: [
                { value: 1, label: __("January") },
                { value: 2, label: __("February") },
                { value: 3, label: __("March") },
                { value: 4, label: __("April") },
                { value: 5, label: __("May") },
                { value: 6, label: __("June") },
                { value: 7, label: __("July") },
                { value: 8, label: __("August") },
                { value: 9, label: __("September") },
                { value: 10, label: __("October") },
                { value: 11, label: __("November") },
                { value: 12, label: __("December") }
            ],
            default: new Date().getMonth() + 1
        },
        {
            fieldname: "year",
            label: __("Year"),
            fieldtype: "Int",
            default: new Date().getFullYear(),
            reqd: 1
        },
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            default: frappe.defaults.get_user_default("Company")
        },
        {
            fieldname: "department",
            label: __("Department"),
            fieldtype: "Link",
            options: "Department"
        },
        {
            fieldname: "summarized_view",
            label: __("Summarized View"),
            fieldtype: "Check",
            default: 0,
            on_change: function () {
                let summarized = frappe.query_report.get_filter_value("summarized_view");
                // When summarized, hide Report Type entirely and always show Month
                frappe.query_report.toggle_filter_display("report_type", summarized);
                if (summarized) {
                    frappe.query_report.toggle_filter_display("month", false);
                } else {
                    // restore Report-Type-dependent toggling
                    let rt = frappe.query_report.get_filter_value("report_type");
                    frappe.query_report.toggle_filter_display("month", rt === "Monthly");
                }
                frappe.query_report.refresh();
            }
        }
    ],

    formatter: function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (value === "✅") {
            value = `<span style="color:#16a34a;font-size:15px">✅</span>`;
        } else if (value === "❌") {
            value = `<span style="color:#dc2626;font-size:15px">❌</span>`;
        } else if (value === "WO") {
            value = `<span style="color:#6b7280;font-weight:600;background:#f3f4f6;padding:2px 6px;border-radius:3px;font-size:11px">WO</span>`;
        } else if (value === "H") {
            value = `<span style="color:#7c3aed;font-weight:600;background:#f3e8ff;padding:2px 6px;border-radius:3px;font-size:11px">H</span>`;
        }

        return value;
    }
};
