// Copyright (c) 2025, BDF and contributors
// For license information, please see license.txt

frappe.ui.form.on("Farmer Billing", {
    refresh(frm) {
        frm.set_df_property('farmer_billing_summary', 'cannot_add_rows', true);
        frm.set_df_property('farmer_billing_details', 'cannot_add_rows', true);
    },
    async do_billing(frm){ 
        await get_milk_entry_data(frm)
    },
    no_of_date: function(frm) {
        if (frm.doc.from_date && frm.doc.no_of_date) {
            let from_date = frappe.datetime.str_to_obj(frm.doc.from_date);
            let to_date = frappe.datetime.add_days(from_date, (frm.doc.no_of_date -1));
            frm.set_value('to_date', frappe.datetime.obj_to_str(to_date));
        } else {
            frappe.throw("Select From Date First")
        }
    },
    from_date: function(frm) {
        if (frm.doc.from_date && frm.doc.no_of_date) {
            let from_date = frappe.datetime.str_to_obj(frm.doc.from_date);
            let to_date = frappe.datetime.add_days(from_date, (frm.doc.no_of_date -1));
            frm.set_value('to_date', frappe.datetime.obj_to_str(to_date));
        }
    }
});

async function get_milk_entry_data(frm) {
    frm.clear_table("farmer_billing_details")
    frm.clear_table("farmer_billing_summary")
    const resp = await frm.call({
        method: 'get_milk_entry_detail_data',
        freeze: true, // Optional: shows a "Processing..." freeze message
        doc: frm.doc,
    });
    frm.refresh(); // Refresh the entire form
}
