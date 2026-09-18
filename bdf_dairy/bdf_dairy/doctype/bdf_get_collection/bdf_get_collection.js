// Copyright (c) 2025, BDF and contributors
// For license information, please see license.txt

const BGC_SHIFT_LABEL = { M: "Morning", E: "Evening" };

frappe.ui.form.on("BDF Get Collection", {
    onload(frm) {
        if (frm.bgc_sync_listener) return;
        frm.bgc_sync_listener = (data) => {
            if (!data || data.name !== frm.doc.name) return;
            if (data.done) {
                frm.dashboard.hide_progress();
                frm.reload_doc();
                frappe.show_alert({ message: __("Sync finished for {0}", [data.name]), indicator: "green" });
            } else if (data.total) {
                frm.dashboard.show_progress(
                    __("Syncing collection"),
                    (data.progress / data.total) * 100,
                    __("{0} of {1}: {2}", [data.progress, data.total, data.warehouse])
                );
            }
        };
        frappe.realtime.on("bdf_get_collection_sync", frm.bgc_sync_listener);
    },

    refresh(frm) {
        if (frm.is_new()) return;

        if (frm.doc.sync_status === "In Progress") {
            frm.dashboard.set_headline(
                __("Sync is running in the background. This page refreshes when it finishes."),
                "blue"
            );
        }

        frm.add_custom_button(__("Sync / Retry All"), () => start_sync(frm));
        frm.add_custom_button(__("Retry Selected"), () => {
            const rows = frm.fields_dict.warehouses.grid.get_selected_children();
            if (!rows.length) {
                frappe.msgprint(__("Tick the warehouse rows you want to retry."));
                return;
            }
            start_sync(frm, rows.map((row) => row.warehouse));
        });
        frm.add_custom_button(
            __("Milk Entries"),
            () => frappe.set_route("List", "Milk Entry", {
                date: frm.doc.date,
                shift: BGC_SHIFT_LABEL[frm.doc.shift],
            }),
            __("View")
        );
    },
});

function start_sync(frm, warehouses) {
    if (frm.is_dirty()) {
        frappe.msgprint(__("Please save the document first."));
        return;
    }
    frm.call({
        method: "start_sync",
        doc: frm.doc,
        args: { warehouses: warehouses || null },
        freeze: true,
    }).then((r) => {
        frappe.show_alert(
            r.message
                ? { message: __("Sync started in the background"), indicator: "blue" }
                : { message: __("A sync is already running for this document"), indicator: "orange" }
        );
        frm.reload_doc();
    });
}
