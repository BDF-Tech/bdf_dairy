frappe.query_reports['Department Report Summary'] = {
    filters: [
        {
            fieldname: 'report_type',
            label: __('Report Type'),
            fieldtype: 'Select',
            options: '\nDaily\nWeekly\nMonthly',
            default: 'Daily'
        },
        {
            fieldname: 'from_date',
            label: __('From Date'),
            fieldtype: 'Date',
            default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
            reqd: 1
        },
        {
            fieldname: 'to_date',
            label: __('To Date'),
            fieldtype: 'Date',
            default: frappe.datetime.get_today(),
            reqd: 1
        },
        {
            fieldname: 'department',
            label: __('Department'),
            fieldtype: 'Link',
            options: 'Department'
        },
        {
            fieldname: 'submitted_to_md',
            label: __('Submitted to MD'),
            fieldtype: 'Check'
        }
    ]
};
