// Copyright (c) 2025, BDF and contributors
// For license information, please see license.txt

frappe.ui.form.on("Farmer Billing", {
    refresh(frm) {
        frm.set_df_property('farmer_billing_summary', 'cannot_add_rows', true);
        frm.set_df_property('farmer_billing_details', 'cannot_add_rows', true);

        if (frm.doc.docstatus === 1) {
            setup_creation_ui(frm);
        }

        if (frm.doc.docstatus === 0 && (frm.doc.farmer_billing_details || []).length) {
            frm.add_custom_button(__('Recalculate Rates'), () => show_rate_preview(frm));
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

// Net Amount is editable: show the adjustment and the new totals straight away
frappe.ui.form.on("Farmer Billing Summary", {
    net_amount(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        frappe.model.set_value(cdt, cdn, "adjustment_amount",
            flt(row.net_amount) - flt(row.amount));
        refresh_totals(frm);
    },
});

function refresh_totals(frm) {
    let adjustment = 0, net = 0;
    (frm.doc.farmer_billing_summary || []).forEach(r => {
        adjustment += flt(r.adjustment_amount);
        net += flt(r.net_amount);
    });
    frm.set_value("total_adjustment", adjustment);
    frm.set_value("total_net_amount", net);
}

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

// Team lead invoices (month-end billing) are tracked on the team rows, not by custom_farmer_billings
function team_invoice_counts(frm) {
    const rows = (frm.doc.team_lead_incentive || []).filter(r => r.month_incentive > 0);
    return { total: rows.length, done: rows.filter(r => r.purchase_invoice).length };
}

function setup_creation_ui(frm) {
    const team = team_invoice_counts(frm);
    const total = (frm.doc.farmer_billing_summary || []).length + team.total;
    if (!total) return;

    frappe.db.count('Purchase Invoice', {
        filters: {
            custom_farmer_billings: frm.doc.name,
            docstatus: ['in', [0, 1]]
        }
    }).then(farmer_done => {
        const done = farmer_done + team.done;
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

    const team = team_invoice_counts(frm);
    const total = (frm.doc.farmer_billing_summary || []).length + team.total;
    const stats = frm._monitor_stats;

    frappe.db.count('Purchase Invoice', {
        filters: {
            custom_farmer_billings: frm.doc.name,
            docstatus: ['in', [0, 1]]
        }
    }).then(farmer_done => {
        const done = farmer_done + team.done;
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


// Shows what re-pricing would change, farmer by farmer, before anything is written
function show_rate_preview(frm) {
    frm.call({
        method: 'preview_milk_rate_changes',
        doc: frm.doc,
        freeze: true,
        freeze_message: __('Checking every Milk Entry against the current Milk Rate...')
    }).then(r => {
        const p = r.message;
        if (!p) return;

        if (!p.changed_entries) {
            frappe.msgprint({
                title: __('Rates Are Up To Date'),
                indicator: 'blue',
                message: __('All {0} Milk Entries already match the Milk Rate that applies today. Nothing to change.', [p.total_entries])
            });
            return;
        }

        const money = v => format_currency(v, frm.doc.currency);
        const sign = v => (v > 0 ? 'green' : 'red');
        const arrow = v => (v > 0 ? '▲' : '▼');

        const rows = p.rows.map(row => `
            <tr>
                <td>${frappe.utils.escape_html(row.farmer_name || row.farmer)}<br>
                    <span class="text-muted small">${row.farmer} · ${row.entries} entries · ${row.qty} L</span></td>
                <td class="text-right">${money(row.old_rate)}<br>
                    <span class="text-muted small">${money(row.old_amount)}</span></td>
                <td class="text-right"><b>${money(row.new_rate)}</b><br>
                    <span class="text-muted small">${money(row.new_amount)}</span></td>
                <td class="text-right" style="color:var(--text-on-${sign(row.difference)}, inherit)">
                    <b>${arrow(row.difference)} ${money(Math.abs(row.difference))}</b></td>
            </tr>`).join('');

        const d = new frappe.ui.Dialog({
            title: __('Recalculate Rates'),
            size: 'large',
            primary_action_label: __('Apply To {0} Entries', [p.changed_entries]),
            primary_action: () => {
                d.hide();
                frm.call({ method: 'recalculate_milk_rates', doc: frm.doc, freeze: true })
                    .then(() => frm.refresh());
            },
            secondary_action_label: __('Cancel'),
            secondary_action: () => d.hide()
        });

        d.$body.html(`
            <p>${__('{0} of {1} Milk Entries would be re-priced, for {2} farmer(s).',
                [p.changed_entries, p.total_entries, p.changed_farmers])}</p>
            ${p.rate_moves.length ? `<p class="text-muted small">${__('Milk Rate')}: ${p.rate_moves.join(', ')}</p>` : ''}
            <table style="width:100%;border-collapse:collapse;margin-bottom:12px;font-size:13px;">
                <tr style="background:var(--bg-light-gray)">
                    <td style="padding:8px"><b>${__('Billing total')}</b></td>
                    <td style="padding:8px;text-align:right">${money(p.old_total)}</td>
                    <td style="padding:8px;text-align:right"><b>${money(p.new_total)}</b></td>
                    <td style="padding:8px;text-align:right"><b>${arrow(p.difference)} ${money(Math.abs(p.difference))}</b></td>
                </tr>
            </table>
            <div style="max-height:360px;overflow:auto">
            <table class="table table-bordered" style="font-size:13px">
                <thead><tr>
                    <th>${__('Farmer')}</th>
                    <th class="text-right">${__('Rate now')}</th>
                    <th class="text-right">${__('New rate')}</th>
                    <th class="text-right">${__('Difference')}</th>
                </tr></thead>
                <tbody>${rows}</tbody>
            </table>
            </div>
            ${p.failed.length ? `<p class="text-danger small">${__('Could not check')}: ${p.failed.join('<br>')}</p>` : ''}
            <p class="text-muted small">${__('Applying updates the Milk Entries themselves. Purchase Receipts keep their original rate.')}</p>
        `);
        d.show();
    });
}
