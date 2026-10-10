frappe.listview_settings["BDF Get Collection"] = {
    add_fields: ["sync_status"],
    get_indicator(doc) {
        const colors = {
            "Not Synced": "gray",
            "In Progress": "blue",
            Synced: "green",
            "Needs Attention": "orange",
            Failed: "red",
        };
        if (doc.sync_status) {
            return [__(doc.sync_status), colors[doc.sync_status] || "gray", "sync_status,=," + doc.sync_status];
        }
    },
};
