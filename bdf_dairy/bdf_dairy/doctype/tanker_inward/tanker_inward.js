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
                        if (row.qty_in_kg) {
                            diff_qty += row.qty_in_kg;
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
    si_fat: function(frm){
        calculate_kg_fat(frm)
    },
    si_snf: function(frm){
        calculate_kg_fat(frm)
    },
    si_qty_in_kg: function(frm){
        calculate_kg_fat(frm)
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
    get_cp_tanker_inwards(frm) {
        open_cp_tanker_inward_dialog(frm);
    },
    cp_collection(frm) {
        if (frm.doc.cp_collection && (frm.doc.milk_received_from_cp_tanker || []).length) {
            frm.clear_table("milk_received_from_cp_tanker");
            frm.refresh_field("milk_received_from_cp_tanker");
            calculate_cp_tanker_totals(frm);
        }
    },
    setup(frm){
        frm.set_query('dcs', 'milk_received_from_tanker', function(){
            return {
                filters: {
                    name: frm.doc.dcs
                }
            }
        })
        frm.set_query('tanker_id', 'milk_received_from_cp_tanker', function(){
            return {
                filters: {
                    docstatus: 1,
                    cp_collection: 1,
                    plant_warehouse: frm.doc.dcs
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
    qty_in_kg: function(frm, cdt, cdn) {
        set_row_litre_and_kg_values(frm, cdt, cdn, 'qty_in_liter', 'milk_received_from_tanker');
    },

    fat: function(frm, cdt, cdn) {
        set_row_litre_and_kg_values(frm, cdt, cdn, 'qty_in_liter', 'milk_received_from_tanker');
    },

    snf: function(frm, cdt, cdn) {
        set_row_litre_and_kg_values(frm, cdt, cdn, 'qty_in_liter', 'milk_received_from_tanker');
    },

    milk_received_from_tanker_add(frm, cdt, cdn) {
        frappe.model.set_value(cdt, cdn, 'dcs', frm.doc.dcs);
    }
});

// All calculations are on KG; litre is display only
function kg_to_litre(kg) {
    const KG_PER_LITRE = 1.03;
    return flt(kg) / KG_PER_LITRE;
}

async function set_row_litre_and_kg_values(frm, cdt, cdn, litre_field, table_field) {
    const row = frappe.get_doc(cdt, cdn);
    const kg = flt(row.qty_in_kg);
    await frappe.model.set_value(cdt, cdn, {
        [litre_field]: kg_to_litre(kg),
        kg_fat: (kg * flt(row.fat)) / 100,
        kg_snf: (kg * flt(row.snf)) / 100
    });
    frm.refresh_field(table_field);
}

frappe.ui.form.on('Other Inward', {
    qty_in_kg: async function(frm, cdt, cdn) {
        await set_row_litre_and_kg_values(frm, cdt, cdn, 'qty_in_litre', 'milk_received_from_cp_tanker');
        calculate_cp_tanker_totals(frm);
    },
    fat: async function(frm, cdt, cdn) {
        await set_row_litre_and_kg_values(frm, cdt, cdn, 'qty_in_litre', 'milk_received_from_cp_tanker');
        calculate_cp_tanker_totals(frm);
    },
    snf: async function(frm, cdt, cdn) {
        await set_row_litre_and_kg_values(frm, cdt, cdn, 'qty_in_litre', 'milk_received_from_cp_tanker');
        calculate_cp_tanker_totals(frm);
    },
    kg_fat: function(frm) {
        calculate_cp_tanker_totals(frm);
    },
    kg_snf: function(frm) {
        calculate_cp_tanker_totals(frm);
    },
    milk_received_from_cp_tanker_remove: function(frm) {
        calculate_cp_tanker_totals(frm);
    }
});

function open_cp_tanker_inward_dialog(frm) {
    if (!frm.doc.dcs || !frm.doc.milk_type) {
        frappe.msgprint(__("Please select DCS and Milk Type first."));
        return;
    }

    let load_cp_tanker_inwards;
    const dialog = new frappe.ui.Dialog({
        title: __("Get CP Tanker Inwards"),
        size: "extra-large",
        fields: [
            {
                fieldname: "from_date",
                fieldtype: "Date",
                label: __("From Date"),
                default: frm.doc.from_date,
                reqd: 1,
                onchange: () => load_cp_tanker_inwards && load_cp_tanker_inwards()
            },
            { fieldtype: "Column Break" },
            {
                fieldname: "to_date",
                fieldtype: "Date",
                label: __("To Date"),
                default: frm.doc.to_date,
                reqd: 1,
                onchange: () => load_cp_tanker_inwards && load_cp_tanker_inwards()
            },
            { fieldtype: "Column Break" },
            {
                fieldname: "cp_warehouses",
                fieldtype: "MultiSelectList",
                label: __("CP Warehouse"),
                description: __("Leave empty to show all CP warehouses"),
                get_data: (txt) => frappe.db.get_link_options("Warehouse", txt, { custom_cp_warehouse: 1 }),
                onchange: () => load_cp_tanker_inwards && load_cp_tanker_inwards()
            },
            { fieldtype: "Section Break" },
            {
                fieldname: "cp_inwards",
                fieldtype: "Table",
                label: __("CP Tanker Inwards sent to {0}", [frm.doc.dcs]),
                allow_bulk_edit: false,
                cannot_add_rows: true,
                cannot_delete_rows: true,
                in_place_edit: true,
                data: [],
                fields: [
                    { fieldname: "tanker_id", fieldtype: "Link", options: "Tanker Inward", label: __("Tanker ID"), read_only: 1, in_list_view: 1, columns: 2 },
                    { fieldname: "dcs", fieldtype: "Link", options: "Warehouse", label: __("CP"), read_only: 1, in_list_view: 1, columns: 2 },
                    { fieldname: "from_date", fieldtype: "Date", label: __("Date"), read_only: 1, in_list_view: 1, columns: 1 },
                    { fieldname: "qty_in_kg", fieldtype: "Float", label: __("Qty in KG"), read_only: 1, in_list_view: 1, columns: 1 },
                    { fieldname: "fat", fieldtype: "Float", label: __("FAT"), read_only: 1, in_list_view: 1, columns: 1 },
                    { fieldname: "snf", fieldtype: "Float", label: __("SNF"), read_only: 1, in_list_view: 1, columns: 1 },
                    { fieldname: "kg_fat", fieldtype: "Float", label: __("KG FAT"), read_only: 1, in_list_view: 1, columns: 1 },
                    { fieldname: "kg_snf", fieldtype: "Float", label: __("KG SNF"), read_only: 1, in_list_view: 1, columns: 1 },
                    { fieldname: "to_date", fieldtype: "Date", label: __("To Date"), read_only: 1 }
                ]
            }
        ],
        primary_action_label: __("Add Selected"),
        primary_action() {
            const selected = dialog.fields_dict.cp_inwards.grid.get_selected_children();
            if (!selected.length) {
                frappe.msgprint(__("Please select at least one CP Tanker Inward."));
                return;
            }

            selected.forEach(row => {
                frm.add_child("milk_received_from_cp_tanker", {
                    tanker_id: row.tanker_id,
                    dcs: row.dcs,
                    qty_in_kg: row.qty_in_kg,
                    qty_in_litre: kg_to_litre(row.qty_in_kg),
                    fat: row.fat,
                    snf: row.snf,
                    kg_fat: row.kg_fat,
                    kg_snf: row.kg_snf
                });
            });

            frm.refresh_field("milk_received_from_cp_tanker");
            calculate_cp_tanker_totals(frm);
            dialog.hide();
        }
    });

    load_cp_tanker_inwards = frappe.utils.debounce(() => {
        const values = dialog.get_values(true);
        const grid = dialog.fields_dict.cp_inwards.grid;
        if (!values.from_date || !values.to_date) {
            grid.df.data = [];
            grid.refresh();
            return;
        }

        frappe.call({
            method: "bdf_dairy.bdf_dairy.doctype.tanker_inward.tanker_inward.get_cp_tanker_inwards",
            args: {
                from_date: values.from_date,
                to_date: values.to_date,
                bmc_warehouse: frm.doc.dcs,
                milk_type: frm.doc.milk_type,
                current_name: frm.is_new() ? null : frm.doc.name,
                cp_warehouses: values.cp_warehouses || []
            },
            callback(r) {
                const already_added = new Set(
                    (frm.doc.milk_received_from_cp_tanker || []).map(row => row.tanker_id)
                );
                grid.df.data = (r.message || []).filter(row => !already_added.has(row.tanker_id));
                grid.refresh();
            }
        });
    }, 300);

    dialog.show();
    load_cp_tanker_inwards();
}

function calculate_cp_tanker_totals(frm) {
    let total_kg = 0;
    let total_kg_fat = 0;
    let total_kg_snf = 0;

    (frm.doc.milk_received_from_cp_tanker || []).forEach(row => {
        total_kg += flt(row.qty_in_kg);
        total_kg_fat += flt(row.kg_fat);
        total_kg_snf += flt(row.kg_snf);
    });

    frm.set_value("total_qty_in_litre1", kg_to_litre(total_kg));
    frm.set_value("total_qty_in_kg1", total_kg);
    frm.set_value("kg_fat1", total_kg_fat);
    frm.set_value("kg_snf1", total_kg_snf);
    frm.set_value("fat1", total_kg > 0 ? (total_kg_fat / total_kg) * 100 : 0);
    frm.set_value("snf1", total_kg > 0 ? (total_kg_snf / total_kg) * 100 : 0);

    calculate_final_totals(frm);
}


function calculate_kg_fat(frm) {
  let qty_in_kg = flt(frm.doc.si_qty_in_kg);
  let kg_fat = (qty_in_kg * flt(frm.doc.si_fat)) / 100;
  let kg_snf = (qty_in_kg * flt(frm.doc.si_snf)) / 100;
  frm.set_value("si_qty_in_liter", kg_to_litre(qty_in_kg));
  frm.set_value("si_kg_fat", kg_fat);
  frm.set_value("si_kg_snf", kg_snf);
}

function calculate_kg_snf(frm) {
  let qty_in_kg = flt(frm.doc.sr_qty_in_kg);
  let kg_fat = (qty_in_kg * flt(frm.doc.sr_fat)) / 100;
  let kg_snf = (qty_in_kg * flt(frm.doc.sr_snf)) / 100;
  frm.set_value("sr_qty_in_liter", kg_to_litre(qty_in_kg));
  frm.set_value("sr_kg_fat", kg_fat);
  frm.set_value("sr_kg_snf", kg_snf);
}

function calculate_final_totals(frm) {

    // DCS part from the rows, so repeated calls never add CP milk twice
    let dcs_kg = 0;
    let dcs_kg_fat = 0;
    let dcs_kg_snf = 0;
    (frm.doc.milk_received_from_dcs || []).forEach(row => {
        dcs_kg += flt(row.qty_in_kg);
        dcs_kg_fat += flt(row.kg_fat);
        dcs_kg_snf += flt(row.kg_snf);
    });

    let other_kg = frm.doc.total_qty_in_kg1 || 0;
    let other_kg_fat = frm.doc.kg_fat1 || 0;
    let other_kg_snf = frm.doc.kg_snf1 || 0;

    let final_kg = dcs_kg + other_kg;
    let final_kg_fat = dcs_kg_fat + other_kg_fat;
    let final_kg_snf = dcs_kg_snf + other_kg_snf;

    let final_fat = final_kg > 0 ? (final_kg_fat / final_kg) * 100 : 0;
    let final_snf = final_kg > 0 ? (final_kg_snf / final_kg) * 100 : 0;

    frm.set_value("total_qty_in_liter", kg_to_litre(final_kg));
    frm.set_value("total_qty_in_kg", final_kg);
    frm.set_value("kg_fat", final_kg_fat);
    frm.set_value("kg_snf", final_kg_snf);
    frm.set_value("fat", final_fat);
    frm.set_value("snf", final_snf);
}
