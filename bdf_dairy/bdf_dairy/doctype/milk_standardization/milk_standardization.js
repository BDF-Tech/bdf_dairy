// Copyright (c) 2025, BDF and contributors
// For license information, please see license.txt








// frappe.ui.form.on('Milk Standardization', {
//     milk_ltr(frm){
//         frm.set_value('milk_kg', frm.doc.milk_ltr*1.03);
//     }
// });

// frappe.ui.form.on('Milk Standardization Calculation', {
//     item_code: function(frm, cdt, cdn) {
//         get_stock_qty(frm, cdt, cdn);
//     },
//     source_warehouse: function(frm, cdt, cdn) {
//         get_stock_qty(frm, cdt, cdn);
//     }
// });

// frappe.ui.form.on('Milk Standardization Details', {
//     qty(frm, cdt, cdn) {
//         frappe.model.set_value(cdt, cdn, 'qty_kg', row.qty * 1.03);
//         update_fat_snf(cdt, cdn);
//     },
//     fat(frm, cdt, cdn) {
//         update_fat_snf(cdt, cdn);
//     },
//     snf(frm, cdt, cdn) {
//         update_fat_snf(cdt, cdn);
//     },
// });

// function update_fat_snf(cdt, cdn) {
//     let row = locals[cdt][cdn];
//     if (row.qty && row.fat) {
//         frappe.model.set_value(cdt, cdn, 'kg_fat', ((row.qty* 1.03) * row.fat / 100));
//     }
//     if (row.qty && row.snf) {
//         frappe.model.set_value(cdt, cdn, 'kg_snf', ((row.qty* 1.03) * row.snf / 100));
//     }
//     frm.refresh_fields()
// }

// function calculate_amount(cdt, cdn) {
//     let row = locals[cdt][cdn];
//     if(row.rate && row.qty){
//         frappe.model.set_value(cdt, cdn, 'amount', (row.qty * row.rate));
//     }
//     frm.refresh_fields()
// }

// function get_stock_qty(frm, cdt, cdn) {
//     let row = locals[cdt][cdn];

//     if (!row.item_code || !row.source_warehouse) {
//         return;
//     }

//     frappe.call({
//         method: "erpnext.stock.utils.get_stock_balance",
//         args: {
//             item_code: row.item_code,
//             warehouse: row.source_warehouse,
//             posting_date: frm.doc.date || frappe.datetime.get_today(),
//         },
//         callback: function(r) {
//             if (r.message) {
//                 frappe.model.set_value(cdt, cdn, "available_qty", r.message);
//             }
//         }
//     });
// }
