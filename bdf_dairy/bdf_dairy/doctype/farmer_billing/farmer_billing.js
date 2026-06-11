// Copyright (c) 2025, BDF and contributors
// For license information, please see license.txt

frappe.ui.form.on("Farmer Billing", {
    refresh(frm) {
        frm.set_df_property('farmer_billing_summary', 'cannot_add_rows', true);
        frm.set_df_property('farmer_billing_details', 'cannot_add_rows', true);

        if (frm.doc.docstatus === 1) {
            setup_creation_ui(frm);
        }
    },
    async do_billing(frm) {
        await get_milk_entry_data(frm);
    },
    no_of_date: function (frm) {
        if (frm.doc.from_date && frm.doc.no_of_date) {
            let from_date = frappe.datetime.str_to_obj(frm.doc.from_date);
            let to_date = frappe.datetime.add_days(from_date, (frm.doc.no_of_date - 1));
            frm.set_value('to_date', frappe.datetime.obj_to_str(to_date));
        } else {
            frappe.throw("Select From Date First")
        }
    },
    from_date: function (frm) {
        if (frm.doc.from_date && frm.doc.no_of_date) {
            let from_date = frappe.datetime.str_to_obj(frm.doc.from_date);
            let to_date = frappe.datetime.add_days(from_date, (frm.doc.no_of_date - 1));
            frm.set_value('to_date', frappe.datetime.obj_to_str(to_date));
        }
    }
});

async function get_milk_entry_data(frm) {
    frm.clear_table("farmer_billing_details");
    frm.clear_table("farmer_billing_summary");
    await frm.call({
        method: 'get_milk_entry_detail_data',
        freeze: true,
        doc: frm.doc,
    });
    frm.refresh();
}

function setup_creation_ui(frm) {
    const total = (frm.doc.farmer_billing_summary || []).length;
    if (!total) return;

    frappe.db.count('Purchase Invoice', {
        filters: {
            custom_farmer_billings: frm.doc.name,
            docstatus: ['in', [0, 1]]
        }
    }).then(done => {
        const pending = total - done;

        frm.dashboard.add_indicator(
            __(`Invoices: ${done} of ${total}`) +
            (pending > 0 ? ' — auto-creating...' : ' — complete'),
            pending > 0 ? 'blue' : 'green'
        );

        if (pending <= 0) return;

        frm.add_custom_button(
            __('Retry Now') + ` (${pending})`,
            () => trigger_retry(frm)
        ).addClass('btn-warning');

        frm.add_custom_button(
            __('Show Monitor'),
            () => show_monitor_dialog(frm)
        );

        if (!frm._monitor_dialog) {
            show_monitor_dialog(frm);
        }

        if (!frm._auto_retry_in_flight) {
            frm._auto_retry_in_flight = true;
            setTimeout(() => trigger_retry(frm), 30000);
        }
    });
}

function trigger_retry(frm) {
    if (frm._monitor_stats) {
        frm._monitor_stats.retry_count++;
        frm._monitor_stats.last_retry_at = Date.now();
    }
    frappe.call({
        method: 'retry_pending_invoices',
        doc: frm.doc,
        callback: () => {
            frm._auto_retry_in_flight = false;
            frm.reload_doc();
        },
        error: () => {
            frm._auto_retry_in_flight = false;
            setTimeout(() => frm.reload_doc(), 5000);
        }
    });
}

function show_monitor_dialog(frm) {
    if (frm._monitor_dialog) {
        frm._monitor_dialog.show();
        return;
    }

    if (!frm._monitor_stats) {
        frm._monitor_stats = {
            retry_count: 0,
            start_time: Date.now(),
            last_retry_at: null,
            history: []
        };
    }

    const d = new frappe.ui.Dialog({
        title: __('Invoice Creation Monitor'),
        primary_action_label: __('Close Monitor'),
        primary_action: () => {
            d.hide();
        }
    });

    d.$body.html('<div class="monitor-content" style="padding: 5px;"></div>');
    d.show();

    frm._monitor_dialog = d;

    d.$wrapper.on('hidden.bs.modal', () => {
        clearInterval(frm._monitor_interval);
        frm._monitor_interval = null;
    });

    update_monitor(frm);
    frm._monitor_interval = setInterval(() => update_monitor(frm), 2000);
}

function update_monitor(frm) {
    if (!frm._monitor_dialog) return;

    const total = (frm.doc.farmer_billing_summary || []).length;
    const stats = frm._monitor_stats;

    frappe.db.count('Purchase Invoice', {
        filters: {
            custom_farmer_billings: frm.doc.name,
            docstatus: ['in', [0, 1]]
        }
    }).then(done => {
        const pending = total - done;
        const now = Date.now();

        stats.history.push({ count: done, ts: now });
        if (stats.history.length > 30) stats.history.shift();

        let avg_per_pi = null;
        if (stats.history.length > 1) {
            const first = stats.history[0];
            const last = stats.history[stats.history.length - 1];
            const time_diff_s = (last.ts - first.ts) / 1000;
            const count_diff = last.count - first.count;
            if (count_diff > 0) avg_per_pi = time_diff_s / count_diff;
        }

        const elapsed = Math.round((now - stats.start_time) / 1000);
        const eta = (avg_per_pi && pending > 0) ? Math.round(avg_per_pi * pending) : null;
        const progress = total > 0 ? (done / total) * 100 : 0;

        const html = `
            <div style="background:#eee;border-radius:4px;height:22px;margin-bottom:18px;overflow:hidden;">
                <div style="background:${pending > 0 ? '#2196f3' : '#4caf50'};width:${progress}%;height:100%;transition:width 0.4s;text-align:center;color:white;font-size:12px;line-height:22px;">
                    ${progress.toFixed(1)}%
                </div>
            </div>
            <table style="width:100%;font-size:13px;border-collapse:collapse;">
                <tr><td style="padding:6px 4px;"><b>Done</b></td><td style="padding:6px 4px;text-align:right;">${done} of ${total}</td></tr>
                <tr style="background:#f9f9f9;"><td style="padding:6px 4px;"><b>Pending</b></td><td style="padding:6px 4px;text-align:right;">${pending}</td></tr>
                <tr><td style="padding:6px 4px;"><b>Elapsed Time</b></td><td style="padding:6px 4px;text-align:right;">${format_time(elapsed)}</td></tr>
                <tr style="background:#f9f9f9;"><td style="padding:6px 4px;"><b>Avg Time per PI</b></td><td style="padding:6px 4px;text-align:right;">${avg_per_pi ? avg_per_pi.toFixed(1) + 's' : '—'}</td></tr>
                <tr><td style="padding:6px 4px;"><b>Estimated Time Left</b></td><td style="padding:6px 4px;text-align:right;">${eta ? format_time(eta) : '—'}</td></tr>
                <tr style="background:#f9f9f9;"><td style="padding:6px 4px;"><b>Retry Calls Fired</b></td><td style="padding:6px 4px;text-align:right;">${stats.retry_count}</td></tr>
                <tr><td style="padding:6px 4px;"><b>Status</b></td><td style="padding:6px 4px;text-align:right;color:${pending > 0 ? '#2196f3' : '#4caf50'};font-weight:bold;">${pending > 0 ? 'Auto-creating...' : '✓ Complete'}</td></tr>
            </table>
        `;
        frm._monitor_dialog.$body.find('.monitor-content').html(html);

        if (pending === 0) {
            clearInterval(frm._monitor_interval);
            frm._monitor_interval = null;
        }
    });
}

function format_time(seconds) {
    if (seconds < 60) return `${seconds}s`;
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}m ${s}s`;
}
