frappe.ui.form.on('Vendor Purchase', {
    fetch_milk_entry_data(frm){
        frm.call({
        method: "fetch_milk_entry_data",
        doc: frm.doc,
        callback: function (r) {
            if (r.message) {
                frm.refresh_fields();
            }
        }
    });
    }
});

frappe.ui.form.on('Vendor Purchase Milk Entry Details', {
    quantity(frm, cdt, cdn) {
        update_fat_snf(cdt, cdn);
        calculate_amount(cdt, cdn); 
    },
    fat(frm, cdt, cdn) {
        update_fat_snf(cdt, cdn);
    },
    snf(frm, cdt, cdn) {
        update_fat_snf(cdt, cdn);
    },
    rate(frm, cdt, cdn) {
        calculate_amount(cdt, cdn);
    }
});

frappe.ui.form.on('Vendor Purchase Details', {
    quantity(frm, cdt, cdn) {
        update_fat_snf(cdt, cdn);
        calculate_amount(cdt, cdn);
    },
    fat(frm, cdt, cdn) {
        update_fat_snf(cdt, cdn);
    },
    snf(frm, cdt, cdn) {
        update_fat_snf(cdt, cdn);
    },
    rate(frm, cdt, cdn) {
        calculate_amount(cdt, cdn);
    }
});

// Update kg_fat and kg_snf based on quantity, fat, snf
function update_fat_snf(cdt, cdn) {
    let row = locals[cdt][cdn];
    let quantity = flt(row.quantity);
    let fat = flt(row.fat);
    let snf = flt(row.snf);
    
    
    frappe.model.set_value(cdt, cdn, 'quantity_kg', (quantity * 1.03));
    frappe.model.set_value(cdt, cdn, 'kg_fat', ((quantity * 1.03) * fat / 100));
    frappe.model.set_value(cdt, cdn, 'kg_snf', ((quantity * 1.03) * snf / 100));
}

// Calculate amount = quantity * rate
function calculate_amount(cdt, cdn) {
    let row = locals[cdt][cdn];
    let quantity = flt(row.quantity);
    let rate = flt(row.rate);

    frappe.model.set_value(cdt, cdn, 'amount', quantity * rate);
}
