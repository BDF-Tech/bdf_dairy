// Copyright (c) 2025, BDF and contributors
// For license information, please see license.txt

frappe.ui.form.on("Farmer Billing", {
    refresh(frm) {
        frm.set_df_property('farmer_billing_summary', 'cannot_add_rows', true);
        frm.set_df_property('farmer_billing_details', 'cannot_add_rows', true);

        // Show "Retry Pending Invoices" button only if status is Partial or Failed
        if (frm.doc.docstatus === 1 &&
            (frm.doc.creation_status === 'Partial' || frm.doc.creation_status === 'Failed')) {
            const total = (frm.doc.farmer_billing_summary || []).length;
            frappe.db.count('Purchase Invoice', {
                filters: {
                    custom_farmer_billings: frm.doc.name,
                    docstatus: ['in', [0, 1]]
                }
            }).then(done => {
                const pending = total - done;
                if (pending > 0) {
                    frm.add_custom_button(
                        __('Retry Pending Invoices') + ` (${pending})`,
                        () => {
                            frappe.confirm(
                                __(`Retry creating the ${pending} missing Purchase Invoice(s)?`),
                                () => {
                                    frappe.call({
                                        method: 'retry_pending_invoices',
                                        doc: frm.doc,
                                        freeze: true,
                                        freeze_message: __('Creating remaining invoices...'),
                                        callback: () => frm.reload_doc()
                                    });
                                }
                            );
                        }
                    ).addClass('btn-warning');
                }
            });
        }

        // Visual indicator for creation status
        if (frm.doc.docstatus === 1 && frm.doc.creation_status) {
            const colors = {
                'Pending': 'orange',
                'In Progress': 'blue',
                'Completed': 'green',
                'Partial': 'orange',
                'Failed': 'red'
            };
            frm.dashboard.add_indicator(
                __(`Invoice Creation: ${frm.doc.creation_status}`) +
                (frm.doc.creation_progress ? ` — ${frm.doc.creation_progress}` : ''),
                colors[frm.doc.creation_status] || 'gray'
            );
        }
    },
    async do_billing(frm) {
        await get_milk_entry_data(frm);
    },
    no_of_date: function (frm) {
        if (frm.doc.from_date && frm.doc.no_of_date) {
            let from_date = frappe.datetime.str_to_obj(frm.doc.from_date);
            let to_date = frappe.datetime.add_days(from_date, (frm.doc.no_of_date - 1));
            frm.set_value('to_date', frappe.datetime.obj_to_str(to_date));
        } else {
            frappe.throw("Select From Date First")
        }
    },
    from_date: function (frm) {
        if (frm.doc.from_date && frm.doc.no_of_date) {
            let from_date = frappe.datetime.str_to_obj(frm.doc.from_date);
            let to_date = frappe.datetime.add_days(from_date, (frm.doc.no_of_date - 1));
            frm.set_value('to_date', frappe.datetime.obj_to_str(to_date));
        }
    }
});

async function get_milk_entry_data(frm) {
    frm.clear_table("farmer_billing_details");
    frm.clear_table("farmer_billing_summary");
    await frm.call({
        method: 'get_milk_entry_detail_data',
        freeze: true,
        doc: frm.doc,
    });
    frm.refresh();
}
