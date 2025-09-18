// Copyright (c) 2024, BDF and contributors
// For license information, please see license.txt

frappe.ui.form.on('Minimum Order Quantity', {
    customer_group: function (frm) {
        if (frm.doc.customer_group) {
            set_filters(frm, 'customer', 'customers',[['Customer', 'customer_group', '=', frm.doc.customer_group], ['Customer', 'disabled', '=', 0]])
        }
    },
    get_all_customer: function (frm) {
        if (frm.doc.customer_group) {
            frm.call({
                method: "get_all_customer",
                doc: frm.doc  
            })
        }
    }
});

function set_filters(frm, DocTypeFieldName, DocTypeField, filters){
    if(DocTypeField !== 'None'){
        frm.set_query(DocTypeFieldName, DocTypeField, function(doc, cdt, cdn) {
            return {
                filters: filters
            };
        });
    } else{
        frm.set_query(DocTypeFieldName, function(doc) {
            return {
                filters: filters,
            };
        });
    }
}
