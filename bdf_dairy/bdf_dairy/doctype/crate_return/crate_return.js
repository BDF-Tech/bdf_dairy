// Copyright (c) 2025, BDF and contributors
// For license information, please see license.txt

frappe.ui.form.on('Crate Return', {
	bdf_gate_pass: function(frm) {
		if(frm.doc.bdf_gate_pass){
			frm.call({
				method: 'get_all_customer',
				doc: frm.doc,
				callback: function(resp){
					frm.set_query('customer', function () {
						return {
							filters: {
								'name': ['in', resp.message[0]] 
							}  
						}
					});
					frm.set_query('warehouse', function () {
						return {
							filters: {
								'name': ['in', resp.message[1]] 
							}
						}
					});
				}
			})
		}
	},
	customer(frm) {
		if(frm.doc.customer && frm.doc.crate_type){
			frm.call({
				method: 'get_opening_qty',
				doc: frm.doc,
				callback: function(resp){
					frappe.model.set_value(frm.doc.doctype, frm.doc.name, 'opening_quantity', resp.message)
				}
			})
		}
	},
	warehouse(frm) {
		if(frm.doc.warehouse && frm.doc.crate_type){
			frm.call({
				method: 'get_warehouse_opening_qty',
				doc: frm.doc,
				callback: function(resp){
					frappe.model.set_value(frm.doc.doctype, frm.doc.name, 'opening_quantity', resp.message)
				}
			})
		}
	},
	crate_type(frm) {
		if(frm.doc.customer && frm.doc.crate_type){
			frm.call({
				method: 'get_opening_qty',
				doc: frm.doc,
				callback: function(resp){
					frappe.model.set_value(frm.doc.doctype, frm.doc.name, 'opening_quantity', resp.message)
				}
			})
		}

		if(frm.doc.warehouse && frm.doc.crate_type){
			frm.call({
				method: 'get_warehouse_opening_qty',
				doc: frm.doc,
				callback: function(resp){
					frappe.model.set_value(frm.doc.doctype, frm.doc.name, 'opening_quantity', resp.message)
				}
			})
		}
	},
	return_quantity(frm){
		frappe.model.set_value(frm.doc.doctype, frm.doc.name, 'balance_quantity', frm.doc.opening_quantity - frm.doc.return_quantity)
	}
});