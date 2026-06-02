// Copyright (c) 2024, BDF and contributors
// For license information, please see license.txt
frappe.ui.form.on('Tanker Inward', {
    async refresh(frm) {
        try {
            // Get linked stock entries
            const linkedStockEntriesResponse = await frappe.call({
                method: "get_linked_stock_entries",  
                doc: frm.doc
            });
  
            if (linkedStockEntriesResponse.message < 2 && frm.doc.docstatus === 1) { 
                
                const materialReceiptResponse = await frm.call({
                    method: 'get_material_receipt',
                    doc: frm.doc,
                });
                console.log(materialReceiptResponse.message)
                if (materialReceiptResponse.message > 0 && frm.doc.docstatus === 1) {
                    frm.add_custom_button('Stock Receipt To Tanker', () => {
                        frm.call({
                            method: 'material_receipt_to_tanker',
                            doc: frm.doc
                        });
                    });
                }

                frm.add_custom_button('Stock Entry To Tanker', () => {
                    frm.call({
                        method: 'material_transfer_from_dcs_to_tanker',
                        doc: frm.doc
                    });
                });
    
                frm.add_custom_button('Stock Entry To Plant', () => {
                    let diff_qty = 0;
                    (frm.doc.difference_of_dcs_and_tanker_milk_received || []).forEach(row => {
                        if (row.qty_in_liter) {
                            diff_qty += row.qty_in_liter;
                        }
                    });
                    let qty = 0;
                    if (diff_qty > 0) {
                        qty = Math.round(diff_qty * 1000) / 1000; 
                    } else if (diff_qty < 0) {
                        qty = 0;
                    }
                    
                    frm.call({
                        method: 'material_transfer_from_tanker_to_plant',
                        doc: frm.doc,
                        args: { qty: qty },
                        freeze: true,
                        freeze_message: __("Processing Stock Entry...")
                    });
                });

            }
        } catch (error) {
            console.error("Error in refresh:", error);
        }
    },
    si_qty_in_liter: function(frm){
        calculate_kg_fat(frm)
    },
    si_fat: function(frm){
        calculate_kg_fat(frm)
    },
    si_snf: function(frm){
        calculate_kg_fat(frm)
    },
    si_qty_in_kg: function(frm){
        calculate_kg_fat(frm)
    },
    
    sr_qty_in_liter: function(frm){
        calculate_kg_snf(frm)
    },
    sr_fat: function(frm){
        calculate_kg_snf(frm)
    },
    sr_snf: function(frm){
        calculate_kg_snf(frm)
    },
    sr_qty_in_kg: function(frm){
        calculate_kg_snf(frm)
    },
    get_sales_summary(frm){
        frm.call({
            method: 'get_sales_summary',
            doc: frm.doc,
            callback: function(response){
                frm.refresh_field('milk_sales_summary')
            }
        })
    },
    setup(frm){
        frm.set_query('dcs', 'milk_received_from_tanker', function(){
            return {
                filters: {
                    name: frm.doc.dcs
                }
            }
        })
    },
    before_save(frm){
        const today = new Date();
        const formattedDate = today.toISOString().split('T')[0];
        frm.set_value('tanker_inward_date', formattedDate)
    },
    before_submit(frm){
        const today = new Date();
        const formattedDate = today.toISOString().split('T')[0];
        frm.set_value('tanker_inward_date', formattedDate)
    },
    from_date: function(frm) {
        if(frm.doc.from_date && frm.doc.to_date && frm.doc.from_shift && frm.doc.to_shift && frm.doc.milk_type && frm.doc.dcs){
            get_milk_entry_data(frm);
        }
    },
    to_date: function(frm) {
        if(frm.doc.from_date && frm.doc.to_date && frm.doc.from_shift && frm.doc.to_shift && frm.doc.milk_type && frm.doc.dcs){
            get_milk_entry_data(frm);
        }
    },
    from_shift: function(frm) {
        if(frm.doc.from_date && frm.doc.to_date && frm.doc.from_shift && frm.doc.to_shift && frm.doc.milk_type && frm.doc.dcs){
            get_milk_entry_data(frm);
        }
    },
    to_shift: function(frm) {
        if(frm.doc.from_date && frm.doc.to_date && frm.doc.from_shift && frm.doc.to_shift && frm.doc.milk_type && frm.doc.dcs){
            get_milk_entry_data(frm);
        }
    },
    milk_type: function(frm) {
        if(frm.doc.from_date && frm.doc.to_date && frm.doc.from_shift && frm.doc.to_shift && frm.doc.milk_type && frm.doc.dcs){
            get_milk_entry_data(frm);
        }
    },
    dcs: function(frm) {
        if(frm.doc.from_date && frm.doc.to_date && frm.doc.from_shift && frm.doc.to_shift && frm.doc.milk_type && frm.doc.dcs){
            get_milk_entry_data(frm);
        }
    },
    quantity_of_sales_lit: function(frm){
        frm.set_value('quantity_of_sales_kg', frm.doc.quantity_of_sales_lit * 1.03)
    }
});

function get_milk_entry_data(frm) {
    frm.call({
        method: 'get_milk_entry_data',
        doc: frm.doc,
        callback: function() {
            calculate_final_totals(frm); // 👈 ADD THIS
        }
    });
}



frappe.ui.form.on('Milk Received From Tanker', {
    qty_in_liter: function(frm, cdt, cdn) {
        const row = frappe.get_doc(cdt, cdn);
        row.qty_in_kg = parseFloat(row.qty_in_liter);

        if (row.fat && row.qty_in_liter) {
            updateKgValues(frm, row, cdt, cdn, 'fat', row.fat);
        }
        if (row.snf && row.qty_in_liter) {
            updateKgValues(frm, row, cdt, cdn, 'snf', row.snf);
        }
        frm.refresh_field("milk_received_from_tanker");
    },

    qty_in_kg: function(frm, cdt, cdn) {
        const row = frappe.get_doc(cdt, cdn);
        row.qty_in_liter = parseFloat(row.qty_in_kg);

        if (row.fat && row.qty_in_kg) {
            updateKgValues(frm, row, cdt, cdn, 'fat', row.fat);
        }
        if (row.snf && row.qty_in_kg) {
            updateKgValues(frm, row, cdt, cdn, 'snf', row.snf);
        }
        frm.refresh_field("milk_received_from_tanker");
    },

    fat: function(frm, cdt, cdn) {
        const row = frappe.get_doc(cdt, cdn);
        if (row.fat && row.qty_in_liter) {
            updateKgValues(frm, row, cdt, cdn, 'fat', row.fat);
        }
    },

    snf: function(frm, cdt, cdn) {
        const row = frappe.get_doc(cdt, cdn);
        if (row.snf && row.qty_in_liter) {
            updateKgValues(frm, row, cdt, cdn, 'snf', row.snf);
        }
    },

    milk_received_from_tanker_add(frm, cdt, cdn) {
        frappe.model.set_value(cdt, cdn, 'dcs', frm.doc.dcs);
    }
});

async function updateKgValues(frm, row, cdt, cdn, type, percentage) {
    const kg_value = (row.qty_in_liter * percentage) / 100;
    if (type === 'fat') {
        await frappe.model.set_value(cdt, cdn, 'kg_fat', kg_value);
    } else if (type === 'snf') {
        await frappe.model.set_value(cdt, cdn, 'kg_snf', kg_value);
    }
    frm.refresh_field("milk_received_from_tanker");
}

frappe.ui.form.on('Other Inward', {
    qty_in_litre: function(frm, cdt, cdn) {
        const row = frappe.get_doc(cdt, cdn);
        frappe.model.set_value(cdt, cdn, 'qty_in_kg', parseFloat(row.qty_in_litre) || 0);
        if (row.fat) {
            frappe.model.set_value(cdt, cdn, 'kg_fat', ((row.qty_in_litre || 0) * row.fat) / 100);
        }
        if (row.snf) {
            frappe.model.set_value(cdt, cdn, 'kg_snf', ((row.qty_in_litre || 0) * row.snf) / 100);
        }
        frm.refresh_field("milk_received_from_cp_tanker");
    },

    fat: function(frm, cdt, cdn) {
        const row = frappe.get_doc(cdt, cdn);
        if (row.qty_in_litre) {
            frappe.model.set_value(cdt, cdn, 'kg_fat', (row.qty_in_litre * (row.fat || 0)) / 100);
        }
        frm.refresh_field("milk_received_from_cp_tanker");
    },

    snf: function(frm, cdt, cdn) {
        const row = frappe.get_doc(cdt, cdn);
        if (row.qty_in_litre) {
            frappe.model.set_value(cdt, cdn, 'kg_snf', (row.qty_in_litre * (row.snf || 0)) / 100);
        }
        frm.refresh_field("milk_received_from_cp_tanker");
    }
});


function calculate_kg_fat(frm) {
  let qty_in_kg = frm.doc.si_qty_in_liter;
  let kg_fat = (qty_in_kg * frm.doc.si_fat) / 100;
  let kg_snf = (qty_in_kg * frm.doc.si_snf) / 100;
  frm.set_value("si_qty_in_kg", qty_in_kg);
  frm.set_value("si_kg_fat", kg_fat);
  frm.set_value("si_kg_snf", kg_snf);
}

function calculate_kg_snf(frm) {
  let qty_in_kg = frm.doc.sr_qty_in_liter;
  let kg_fat = (qty_in_kg * frm.doc.sr_fat) / 100;
  let kg_snf = (qty_in_kg * frm.doc.sr_snf) / 100;
  frm.set_value("sr_qty_in_kg", qty_in_kg);
  frm.set_value("sr_kg_fat", kg_fat);
  frm.set_value("sr_kg_snf", kg_snf);
}

function calculate_final_totals(frm) {

    let dcs_litre = frm.doc.total_qty_in_liter || 0;
    let dcs_kg = frm.doc.total_qty_in_kg || 0;
    let dcs_kg_fat = frm.doc.kg_fat || 0;
    let dcs_kg_snf = frm.doc.kg_snf || 0;

    let other_litre = frm.doc.total_qty_in_litre1 || 0;
    let other_kg = frm.doc.total_qty_in_kg1 || 0;
    let other_kg_fat = frm.doc.kg_fat1 || 0;
    let other_kg_snf = frm.doc.kg_snf1 || 0;

    let final_litre = dcs_litre + other_litre;
    let final_kg = dcs_kg + other_kg;
    let final_kg_fat = dcs_kg_fat + other_kg_fat;
    let final_kg_snf = dcs_kg_snf + other_kg_snf;

    let final_fat = final_kg > 0 ? (final_kg_fat / final_kg) * 100 : 0;
    let final_snf = final_kg > 0 ? (final_kg_snf / final_kg) * 100 : 0;

    frm.set_value("total_qty_in_liter", final_litre);
    frm.set_value("total_qty_in_kg", final_kg);
    frm.set_value("kg_fat", final_kg_fat);
    frm.set_value("kg_snf", final_kg_snf);
    frm.set_value("fat", final_fat);
    frm.set_value("snf", final_snf);
}
