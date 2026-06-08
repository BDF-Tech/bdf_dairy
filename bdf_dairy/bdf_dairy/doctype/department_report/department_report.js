frappe.ui.form.on('Department Report', {

    onload: function (frm) {
        // Only show Active employees in the employee picker
        frm.set_query('employee', function () {
            return { filters: { status: 'Active' } };
        });

        if (frm.is_new()) {
            frm.set_value('report_type', 'Daily');
            frm.set_value('report_date', frappe.datetime.get_today());
            frm.set_value('report_year', new Date().getFullYear());
        }
    },

    employee: function (frm) {
        if (!frm.doc.employee) return;

        frappe.db.get_value(
            'Employee',
            frm.doc.employee,
            ['department', 'designation', 'custom_department_head', 'reports_to'],
            function (d) {
                if (d) {
                    frm.set_value('department', d.department);
                    frm.set_value('designation', d.designation);
                    frm.set_value('department_head', d.custom_department_head || '');
                    frm.set_value('reports_to', d.reports_to || '');
                }
            }
        );
    },

    report_type: function (frm) {
        if (frm.doc.report_type === 'Weekly' && !frm.doc.week_start_date) {
            let today = frappe.datetime.get_today();
            let day = new Date(today).getDay();
            let diff = day === 0 ? -6 : 1 - day;
            let monday = frappe.datetime.add_days(today, diff);
            frm.set_value('week_start_date', monday);
        }
        if (frm.doc.report_type === 'Monthly') {
            if (!frm.doc.report_month) {
                let months = ['January', 'February', 'March', 'April', 'May', 'June',
                    'July', 'August', 'September', 'October', 'November', 'December'];
                frm.set_value('report_month', months[new Date().getMonth()]);
            }
        }
    },

    week_start_date: function (frm) {
        if (frm.doc.week_start_date) {
            frm.set_value('week_end_date', frappe.datetime.add_days(frm.doc.week_start_date, 6));
        }
    },

    refresh: function (frm) {
        if (frm.doc.submitted_to_md) {
            frm.dashboard.add_indicator(
                __('Reported to MD on {0}', [frappe.datetime.str_to_user(frm.doc.md_notified_at)]),
                'green'
            );
        }

        if (!frm.is_new()) {
            let period = get_period_label(frm.doc);
            if (period) {
                frm.set_intro(
                    `<b>${frm.doc.report_type} Report</b> &nbsp;|&nbsp; ${frm.doc.department || ''} &nbsp;|&nbsp; ${period}`,
                    'blue'
                );
            }
        }
    }
});

function get_period_label(doc) {
    if (doc.report_type === 'Daily') return doc.report_date || '';
    if (doc.report_type === 'Weekly') {
        return doc.week_start_date && doc.week_end_date
            ? `${doc.week_start_date}  to  ${doc.week_end_date}`
            : '';
    }
    if (doc.report_type === 'Monthly') {
        return doc.report_month && doc.report_year
            ? `${doc.report_month} ${doc.report_year}`
            : '';
    }
    return '';
}
