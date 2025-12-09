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
        doc: frm.doc
    });
}



frappe.ui.form.on('Milk Received From Tanker', {
    qty_in_liter: function(frm, cdt, cdn) {
        const row = frappe.get_doc(cdt, cdn);
        row.qty_in_kg = parseFloat(row.qty_in_liter) * 1.03;

        if (row.fat && row.qty_in_liter && frm.doc.milk_type) {
            updateKgValues(frm, row, cdt, cdn, 'fat', row.fat);
        }
        
        if (row.snf && row.qty_in_liter && frm.doc.milk_type) {
            updateKgValues(frm, row, cdt, cdn, 'snf', row.snf);
        }
        frm.refresh_field("milk_received_from_tanker");
    },
    
    qty_in_kg: function(frm, cdt, cdn) {
        const row = frappe.get_doc(cdt, cdn);
        row.qty_in_liter = parseFloat(row.qty_in_kg) * 0.970874;

        if (row.fat && row.qty_in_liter && frm.doc.milk_type) {
            updateKgValues(frm, row, cdt, cdn, 'fat', row.fat);
        }

        if (row.snf && row.qty_in_liter && frm.doc.milk_type) {
            updateKgValues(frm, row, cdt, cdn, 'snf', row.snf);
        }
        frm.refresh_field("milk_received_from_tanker");
    },

    fat: function(frm, cdt, cdn) {
        const row = frappe.get_doc(cdt, cdn);
        if (row.fat && row.qty_in_liter && frm.doc.milk_type) {
            updateKgValues(frm, row, cdt, cdn, 'fat', row.fat);
        }
    },

    snf: function(frm, cdt, cdn) {
        const row = frappe.get_doc(cdt, cdn);
        if (row.snf && row.qty_in_liter && frm.doc.milk_type) {
            updateKgValues(frm, row, cdt, cdn, 'snf', row.snf);
        }
    },
    milk_received_from_tanker_add(frm, cdt, cdn) {
        const row = frappe.get_doc(cdt, cdn);
        frappe.model.set_value(cdt, cdn, 'dcs', frm.doc.dcs);
    }
});

async function updateKgValues(frm, row, cdt, cdn, type, percentage) {
    const kg_value = ((row.qty_in_liter * 1.03) * percentage)/100;
    if (type === 'fat') {
        await frappe.model.set_value(cdt, cdn, 'kg_fat', kg_value);
    } else if (type === 'snf') {
        await frappe.model.set_value(cdt, cdn, 'kg_snf', kg_value);
    }
    frm.refresh_field("milk_received_from_tanker");
}


function calculate_kg_fat(frm) {
  let kg_fat = (frm.doc.si_qty_in_kg * frm.doc.si_fat)/100;
  let kg_snf = (frm.doc.si_qty_in_kg * frm.doc.si_snf)/100;
  let qty_in_kg = frm.doc.si_qty_in_liter * 1.03
  frm.set_value("si_kg_fat", kg_fat);
  frm.set_value("si_kg_snf", kg_snf);
  frm.set_value("si_qty_in_kg", qty_in_kg);
}

function calculate_kg_snf(frm) {
  let kg_fat = (frm.doc.sr_qty_in_kg * frm.doc.sr_fat) / 100;
  let kg_snf = (frm.doc.sr_qty_in_kg * frm.doc.sr_snf) / 100;
  let qty_in_kg = frm.doc.sr_qty_in_liter * 1.03
  frm.set_value("sr_kg_fat", kg_fat);
  frm.set_value("sr_kg_snf", kg_snf);
  frm.set_value("sr_qty_in_kg", qty_in_kg);
}

