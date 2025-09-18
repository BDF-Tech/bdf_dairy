// Copyright (c) 2025, BDF and contributors
// For license information, please see license.txt

frappe.ui.form.on('Milk Standardization', {
    validate(frm) {
        let total_qty = 0;
        let total_kg_fat = 0;
        let total_kg_snf = 0;

        (frm.doc.milk_standardization_details || []).forEach(row => {
            total_qty += row.qty || 0;
            total_kg_fat += row.kg_fat || 0;
            total_kg_snf += row.kg_snf || 0;
        });

        frm.set_value('total_qty', total_qty);
        frm.set_value('kg_fat', total_kg_fat);
        frm.set_value('kg_snf', total_kg_snf);

        if (total_qty > 0) {
            frm.set_value('fat', (total_kg_fat * 100) / total_qty);
            frm.set_value('snf', (total_kg_snf * 100) / total_qty);
        } else {
            frm.set_value('fat', 0);
            frm.set_value('snf', 0);
        }
    }
});


frappe.ui.form.on('Milk Standardization Details', {
    qty(frm, cdt, cdn) {
        frappe.model.set_value(cdt, cdn, 'qty_kg', row.qty * 1.03);
        update_fat_snf(cdt, cdn);
    },
    fat(frm, cdt, cdn) {
        update_fat_snf(cdt, cdn);
    },
    snf(frm, cdt, cdn) {
        update_fat_snf(cdt, cdn);
    },
});

function update_fat_snf(cdt, cdn) {
    let row = locals[cdt][cdn];

    if (row.qty && row.fat) {
        frappe.model.set_value(cdt, cdn, 'kg_fat', ((row.qty* 1.03) * row.fat / 100));
    }

    if (row.qty && row.snf) {
        frappe.model.set_value(cdt, cdn, 'kg_snf', ((row.qty* 1.03) * row.snf / 100));
    }
}

function calculate_amount(cdt, cdn) {
    let row = locals[cdt][cdn];
    if(row.rate && row.qty){
        frappe.model.set_value(cdt, cdn, 'amount', (row.qty * row.rate));
    }
}