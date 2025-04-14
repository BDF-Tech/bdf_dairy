// Copyright (c) 2025, BDF and contributors
// For license information, please see license.txt

frappe.ui.form.on("Farmer Billing", {
    async do_billing(frm){
        await get_milk_entry_data(frm)
    },
	
});

async function get_milk_entry_data(frm) {
    // try {
        frm.clear_table("farmer_billing_details")
        frm.clear_table("farmer_billing_summary")
        const resp = await frm.call({
            method: 'get_milk_entry_detail_data',
            freeze: true, // Optional: shows a "Processing..." freeze message
            doc: frm.doc,
        });
        console.log("Done", resp);
        frm.refresh(); // Refresh the entire form
    // } catch (error) {
    //     console.error("Error fetching milk entry data:", error);
    // }
}
