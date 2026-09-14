# Copyright (c) 2026, BDF and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, strip_html

from bdf_dairy.bdf_dairy.doctype.tanker_inward.tanker_inward import kg_to_litre

QUALITY_TEST_FIELDS = ("test", "result_sign", "result", "remark")


class CPTankerInwardEntry(Document):
	"""One screen per date + shift + BMC to create the CP Tanker Inwards of every CP in one go."""

	def validate(self):
		self.validate_duplicate_entry()
		self.calculate_rows_and_totals()

	def validate_duplicate_entry(self):
		existing = frappe.db.get_value(
			"CP Tanker Inward Entry",
			{
				"date": self.date,
				"shift": self.shift,
				"bmc_warehouse": self.bmc_warehouse,
				"milk_type": self.milk_type,
				"name": ["!=", self.name],
			},
		)
		if existing:
			frappe.throw(
				_("CP Tanker Inward Entry {0} already exists for {1} {2} {3}. Please use it.").format(
					frappe.bold(existing), self.date, self.shift, self.bmc_warehouse
				)
			)

	def calculate_rows_and_totals(self):
		for row in self.items:
			row.received_kg_fat = flt(row.received_kg) * flt(row.received_fat) / 100
			row.received_kg_snf = flt(row.received_kg) * flt(row.received_snf) / 100
			row.difference_kg = flt(row.received_kg) - flt(row.collected_kg) if flt(row.received_kg) else 0

		self.total_cps = len(self.items)
		self.created_count = len([row for row in self.items if row.tanker_inward])
		self.total_collected_kg = sum(flt(row.collected_kg) for row in self.items)
		self.total_received_kg = sum(flt(row.received_kg) for row in self.items)
		self.total_difference_kg = sum(flt(row.difference_kg) for row in self.items)

	@frappe.whitelist()
	def get_cps(self):
		"""Fill one row per CP of this BMC that has Milk Entries for the date and shift.
		Values already typed for a CP are kept."""
		if not (self.date and self.shift and self.bmc_warehouse and self.milk_type):
			frappe.throw(_("Please set Date, Shift, BMC Warehouse and Milk Type first."))

		cp_warehouses = get_cp_warehouses_for_bmc(self.bmc_warehouse)
		collected = get_collected_milk(cp_warehouses, self.date, self.shift, self.milk_type)
		existing_inwards = get_existing_tanker_inwards(cp_warehouses, self.date, self.shift, self.milk_type)
		last_tests = get_last_quality_tests(cp_warehouses)
		rows_by_cp = {row.cp_warehouse: row for row in self.items}

		new_rows = []
		for cp in sorted(set(collected) | {cp for cp, row in rows_by_cp.items() if row.tanker_inward}):
			milk = collected.get(cp, {})
			old = rows_by_cp.get(cp)
			row = {
				"cp_warehouse": cp,
				"collected_kg": flt(milk.get("kg")),
				"collected_kg_fat": flt(milk.get("kg_fat")),
				"collected_kg_snf": flt(milk.get("kg_snf")),
				"collected_fat": flt(milk.get("kg_fat")) / flt(milk.get("kg")) * 100 if flt(milk.get("kg")) else 0,
				"collected_snf": flt(milk.get("kg_snf")) / flt(milk.get("kg")) * 100 if flt(milk.get("kg")) else 0,
			}
			if old:
				row.update({field: old.get(field) for field in ("received_kg", "received_fat", "received_snf", *QUALITY_TEST_FIELDS, "tanker_inward", "status")})
			else:
				row.update(last_tests.get(cp, {}))

			if not row.get("tanker_inward") and existing_inwards.get(cp):
				row["tanker_inward"] = existing_inwards[cp]
				row["status"] = _("Tanker Inward already exists")
			new_rows.append(row)

		self.set("items", new_rows)
		self.calculate_rows_and_totals()

		if not new_rows:
			frappe.msgprint(
				_("No Milk Entries found for CPs of {0} on {1} {2}. Make sure the CP warehouses are ticked as CP Warehouse and have Sends Milk To (BMC) set.").format(
					self.bmc_warehouse, self.date, self.shift
				)
			)

	@frappe.whitelist()
	def create_tanker_inwards(self):
		"""Create a draft Tanker Inward for every CP row that has Received KG and no Tanker Inward yet."""
		if self.is_new():
			frappe.throw(_("Please save before creating Tanker Inwards."))

		existing_inwards = get_existing_tanker_inwards(
			[row.cp_warehouse for row in self.items], self.date, self.shift, self.milk_type
		)
		created, failed, skipped = [], [], []

		for row in self.items:
			if row.tanker_inward:
				continue
			if existing_inwards.get(row.cp_warehouse):
				row.tanker_inward = existing_inwards[row.cp_warehouse]
				row.status = _("Tanker Inward already exists")
				continue

			missing = self.get_missing_values(row)
			if missing:
				row.status = _("Not created. Missing: {0}").format(", ".join(missing))
				skipped.append(row.cp_warehouse)
				continue

			frappe.db.savepoint("cp_tanker_inward")
			try:
				tanker_inward = self.make_tanker_inward(row)
				row.tanker_inward = tanker_inward.name
				row.status = _("Created")
				created.append(tanker_inward.name)
			except Exception as e:
				frappe.db.rollback(save_point="cp_tanker_inward")
				row.status = _("Error: {0}").format(strip_html(str(e))[:500])
				failed.append(row.cp_warehouse)
			finally:
				frappe.clear_messages()

		self.save()
		return {"created": created, "failed": failed, "skipped": skipped}

	def get_missing_values(self, row):
		labels = {
			"received_kg": _("Received KG"),
			"received_fat": _("Received FAT"),
			"received_snf": _("Received SNF"),
			"test": _("Test"),
			"result_sign": _("Result Sign"),
			"result": _("Result"),
			"remark": _("Remark"),
		}
		return [label for field, label in labels.items() if not row.get(field)]

	def make_tanker_inward(self, row):
		tanker_inward = frappe.new_doc("Tanker Inward")
		tanker_inward.update(
			{
				"from_date": self.date,
				"to_date": self.date,
				"from_shift": self.shift,
				"to_shift": self.shift,
				"milk_type": self.milk_type,
				"dcs": row.cp_warehouse,
				"plant_warehouse": self.bmc_warehouse,
				"excess_warehouse": self.bmc_warehouse,
				"si_dcs": self.bmc_warehouse,
			}
		)
		tanker_inward.get_milk_entry_data()
		tanker_inward.append(
			"milk_received_from_tanker",
			{
				"dcs": row.cp_warehouse,
				"qty_in_kg": row.received_kg,
				"qty_in_liter": kg_to_litre(row.received_kg),
				"fat": row.received_fat,
				"snf": row.received_snf,
				"kg_fat": flt(row.received_kg) * flt(row.received_fat) / 100,
				"kg_snf": flt(row.received_kg) * flt(row.received_snf) / 100,
			},
		)
		tanker_inward.append("tanker_inward_quality_testing", {field: row.get(field) for field in QUALITY_TEST_FIELDS})
		tanker_inward.insert()
		return tanker_inward


def get_cp_warehouses_for_bmc(bmc_warehouse):
	"""CP warehouses whose "Sends Milk To (BMC)" is this BMC. For CPs where it is not set yet,
	fall back to the Plant Warehouse of their latest submitted CP Tanker Inward."""
	cp_warehouses = frappe.get_all(
		"Warehouse",
		filters={"custom_cp_warehouse": 1, "disabled": 0},
		fields=["name", "custom_bmc_warehouse"],
	)
	mapped = [w.name for w in cp_warehouses if w.custom_bmc_warehouse == bmc_warehouse]
	unmapped = [w.name for w in cp_warehouses if not w.custom_bmc_warehouse]
	if unmapped:
		latest_bmc = frappe.db.sql(
			"""
			SELECT ti.dcs, ti.plant_warehouse
			FROM `tabTanker Inward` ti
			INNER JOIN (
				SELECT dcs, MAX(creation) AS creation
				FROM `tabTanker Inward`
				WHERE docstatus = 1 AND cp_collection = 1 AND dcs IN %(unmapped)s
				GROUP BY dcs
			) latest ON latest.dcs = ti.dcs AND latest.creation = ti.creation
			""",
			{"unmapped": unmapped},
			as_dict=True,
		)
		mapped += [d.dcs for d in latest_bmc if d.plant_warehouse == bmc_warehouse]
	return mapped


def get_collected_milk(cp_warehouses, date, shift, milk_type):
	if not cp_warehouses:
		return {}
	rows = frappe.db.sql(
		"""
		SELECT dcs_id AS cp, SUM(volume) AS kg, SUM(fat_kg) AS kg_fat, SUM(snf_kg) AS kg_snf
		FROM `tabMilk Entry`
		WHERE docstatus = 1 AND date = %(date)s AND shift = %(shift)s AND milk_type = %(milk_type)s
			AND dcs_id IN %(cp_warehouses)s
		GROUP BY dcs_id
		HAVING SUM(volume) > 0
		""",
		{"date": date, "shift": shift, "milk_type": milk_type, "cp_warehouses": cp_warehouses},
		as_dict=True,
	)
	return {row.cp: row for row in rows}


def get_existing_tanker_inwards(cp_warehouses, date, shift, milk_type):
	"""Non-cancelled Tanker Inwards already made for a CP for exactly this date and shift."""
	if not cp_warehouses:
		return {}
	rows = frappe.get_all(
		"Tanker Inward",
		filters={
			"dcs": ["in", cp_warehouses],
			"from_date": date,
			"to_date": date,
			"from_shift": shift,
			"to_shift": shift,
			"milk_type": milk_type,
			"docstatus": ["<", 2],
		},
		fields=["name", "dcs"],
		order_by="creation asc",
	)
	return {row.dcs: row.name for row in rows}


def get_last_quality_tests(cp_warehouses):
	"""Test type and remark of each CP's latest Tanker Inward, used to pre-fill its row.
	Result Sign and Result are never pre-filled: every CP is tested for every shift."""
	if not cp_warehouses:
		return {}
	rows = frappe.db.sql(
		"""
		SELECT ti.dcs, q.test, q.remark
		FROM `tabTanker Inward` ti
		INNER JOIN (
			SELECT dcs, MAX(creation) AS creation
			FROM `tabTanker Inward`
			WHERE docstatus = 1 AND dcs IN %(cp_warehouses)s
			GROUP BY dcs
		) latest ON latest.dcs = ti.dcs AND latest.creation = ti.creation
		INNER JOIN `tabTanker Inward Quality Testing` q
			ON q.parent = ti.name AND q.parenttype = 'Tanker Inward' AND q.idx = 1
		""",
		{"cp_warehouses": cp_warehouses},
		as_dict=True,
	)
	return {row.dcs: {"test": row.test, "remark": row.remark} for row in rows}
