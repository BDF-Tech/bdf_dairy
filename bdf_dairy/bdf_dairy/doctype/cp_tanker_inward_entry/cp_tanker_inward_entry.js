// Copyright (c) 2026, BDF and contributors
// For license information, please see license.txt

frappe.ui.form.on("CP Tanker Inward Entry", {
	setup(frm) {
		frm.set_query("bmc_warehouse", () => ({ filters: { is_group: 0, custom_cp_warehouse: 0 } }));
	},

	refresh(frm) {
		const tanker_inwards = (frm.doc.items || []).map((row) => row.tanker_inward).filter(Boolean);
		if (tanker_inwards.length) {
			frm.add_custom_button(__("View Tanker Inwards"), () => {
				frappe.route_options = { name: ["in", tanker_inwards] };
				frappe.set_route("List", "Tanker Inward");
			});
		}
	},

	date(frm) {
		reload_cps_if_ready(frm);
	},
	shift(frm) {
		reload_cps_if_ready(frm);
	},
	bmc_warehouse(frm) {
		reload_cps_if_ready(frm);
	},
	milk_type(frm) {
		reload_cps_if_ready(frm);
	},

	get_cps(frm) {
		get_cps(frm);
	},

	async create_tanker_inwards(frm) {
		if (frm.is_dirty() || frm.is_new()) {
			await frm.save();
		}
		const ready = (frm.doc.items || []).filter((row) => !row.tanker_inward && flt(row.received_kg) > 0);
		if (!ready.length) {
			frappe.msgprint(__("No CP rows with Received KG that still need a Tanker Inward."));
			return;
		}

		frappe.confirm(
			__("Create {0} draft Tanker Inwards for {1} {2}?", [ready.length, frm.doc.date, frm.doc.shift]),
			async () => {
				const r = await frm.call({
					method: "create_tanker_inwards",
					doc: frm.doc,
					freeze: true,
					freeze_message: __("Creating Tanker Inwards..."),
				});
				const { created = [], failed = [], skipped = [] } = r.message || {};
				let message = __("Created {0} draft Tanker Inwards.", [created.length]);
				if (skipped.length) {
					message += "<br>" + __("Skipped (missing values): {0}", [skipped.join(", ")]);
				}
				if (failed.length) {
					message += "<br>" + __("Failed: {0}. See the Status of those rows.", [failed.join(", ")]);
				}
				frappe.msgprint({
					title: __("CP Tanker Inwards"),
					message,
					indicator: failed.length ? "orange" : "green",
				});
				frm.reload_doc();
			}
		);
	},
});

frappe.ui.form.on("CP Tanker Inward Entry Item", {
	received_kg(frm, cdt, cdn) {
		calculate_row(frm, cdt, cdn);
	},
	received_fat(frm, cdt, cdn) {
		calculate_row(frm, cdt, cdn);
	},
	received_snf(frm, cdt, cdn) {
		calculate_row(frm, cdt, cdn);
	},
	items_remove(frm) {
		calculate_totals(frm);
	},
});

function reload_cps_if_ready(frm) {
	// Date, shift, BMC and milk type can only change before the first save
	if (!frm.is_new() || !(frm.doc.date && frm.doc.shift && frm.doc.bmc_warehouse && frm.doc.milk_type)) {
		return;
	}
	frm.clear_table("items");
	get_cps(frm);
}

function get_cps(frm) {
	frm.call({
		method: "get_cps",
		doc: frm.doc,
		freeze: true,
		freeze_message: __("Getting CPs..."),
		callback() {
			frm.refresh_field("items");
			frm.dirty();
		},
	});
}

function calculate_row(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	const kg = flt(row.received_kg);
	row.received_kg_fat = (kg * flt(row.received_fat)) / 100;
	row.received_kg_snf = (kg * flt(row.received_snf)) / 100;
	row.difference_kg = kg ? kg - flt(row.collected_kg) : 0;
	frm.refresh_field("items");
	calculate_totals(frm);
}

function calculate_totals(frm) {
	const rows = frm.doc.items || [];
	const sum = (field) => rows.reduce((total, row) => total + flt(row[field]), 0);
	frm.set_value({
		total_cps: rows.length,
		total_collected_kg: sum("collected_kg"),
		total_received_kg: sum("received_kg"),
		total_difference_kg: sum("difference_kg"),
	});
}
