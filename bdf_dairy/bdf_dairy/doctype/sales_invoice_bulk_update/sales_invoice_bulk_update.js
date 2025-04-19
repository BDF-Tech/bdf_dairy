// Copyright (c) 2025, BDF and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sales Invoice Bulk Update", {
	sales_invoices: function(frm) {
		frm.call({
			method: 'get_sales_invoices_date',
			doc: frm.doc,
		});
	},
    select_all: function(frm) {
		frm.call({
			method: 'selectall',
			doc: frm.doc,
		});
	}
});
