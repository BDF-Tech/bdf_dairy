# Copyright (c) 2025, BDF and contributors
# For license information, please see license.txt

import json
from concurrent.futures import ThreadPoolExecutor

import frappe
import requests
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, cstr, get_link_to_form, getdate, now_datetime, nowdate, strip_html_tags
from frappe.utils.background_jobs import is_job_enqueued
from frappe.utils.synchronization import filelock

DOCTYPE = "BDF Get Collection"
SYNC_EVENT = "bdf_get_collection_sync"
SHIFT_LABEL = {"M": "Morning", "E": "Evening"}
MILK_TYPE_MAP = {"C": "Cow", "B": "Buffalo"}
REQUIRED_KEYS = ("Member_Code", "Milk_Type", "Qty_KG", "Fat", "Snf", "CLR")
MAX_PARALLEL_CALLS = 8


class BDFGetCollection(Document):
	"""One document per date + shift. Each row of `warehouses` is one BMC / CP and shows how
	its last sync went. Sync / Retry only ever adds missing Milk Entries."""

	def before_insert(self):
		name = get_collection_name(self.date, self.shift)
		if frappe.db.exists(DOCTYPE, name):
			frappe.throw(
				_("{0} already exists for this date and shift. Open it and use Retry.").format(
					get_link_to_form(DOCTYPE, name)
				),
				title=_("Already Exists"),
			)
		self.sync_status = "Not Synced"

	def validate(self):
		self.ensure_warehouses()
		self.set_totals()

	def ensure_warehouses(self):
		if self.warehouses:
			return
		if self.warehouse:
			# Legacy record: one warehouse per document.
			self.append("warehouses", {"warehouse": self.warehouse, "mpp_code": self.mpp_code})
		else:
			self.add_mpp_warehouses()

	def add_mpp_warehouses(self):
		present = {row.warehouse for row in self.warehouses}
		for wh in get_mpp_warehouses():
			if wh.name not in present:
				self.append("warehouses", {"warehouse": wh.name, "mpp_code": wh.custom_mpp_code})

	def set_totals(self):
		self.total_api_rows = sum(cint(row.api_rows) for row in self.warehouses)
		self.total_entries = sum(cint(row.entries) for row in self.warehouses)
		self.total_not_created = sum(cint(row.not_created) for row in self.warehouses)

	@frappe.whitelist()
	def start_sync(self, warehouses=None):
		"""Sync / Retry in the background. `warehouses` limits it to the selected rows."""
		self.check_permission("write")
		if self.is_new():
			frappe.throw(_("Save the document before syncing."))
		started = enqueue_sync(self.name, frappe.parse_json(warehouses) if warehouses else None)
		if started:
			self.sync_status = "In Progress"
		return started


def get_collection_name(date, shift):
	return f"BGC-{getdate(date)}-{shift}"


def get_mpp_warehouses():
	"""Active BMC / CP warehouses, i.e. the ones with an MPP Code."""
	return frappe.get_all(
		"Warehouse",
		filters={"disabled": 0, "is_group": 0, "custom_mpp_code": [">", 0]},
		fields=["name", "custom_mpp_code"],
		order_by="name asc",
	)


# ---------------------------------------------------------------------- #
# Scheduler: 12:00 for Morning, 22:00 for Evening (see hooks.py)
# ---------------------------------------------------------------------- #
def sync_morning_collection():
	schedule_sync("M")


def sync_evening_collection():
	schedule_sync("E")


def schedule_sync(shift):
	name = get_collection_name(nowdate(), shift)
	if frappe.db.exists(DOCTYPE, name):
		doc = frappe.get_doc(DOCTYPE, name)
		doc.add_mpp_warehouses()
		doc.save(ignore_permissions=True)
	else:
		doc = frappe.get_doc({"doctype": DOCTYPE, "date": nowdate(), "shift": shift})
		doc.insert(ignore_permissions=True)
	enqueue_sync(doc.name)


# ---------------------------------------------------------------------- #
# Background sync
# ---------------------------------------------------------------------- #
def enqueue_sync(docname, warehouses=None):
	"""Returns False when a sync for this document is already queued or running."""
	job_id = f"bdf_get_collection_sync::{docname}"
	if is_job_enqueued(job_id):
		return False
	frappe.db.set_value(DOCTYPE, docname, "sync_status", "In Progress", update_modified=False)
	frappe.enqueue(
		"bdf_dairy.bdf_dairy.doctype.bdf_get_collection.bdf_get_collection.run_sync",
		queue="long",
		timeout=3600,
		job_id=job_id,
		deduplicate=True,
		enqueue_after_commit=True,
		docname=docname,
		warehouses=warehouses,
	)
	return True


def run_sync(docname, warehouses=None):
	try:
		# The scheduler and a manual Retry can overlap; run them one after the other.
		with filelock(f"bdf_get_collection_sync_{frappe.scrub(docname)}", timeout=600):
			sync_collection(docname, warehouses)
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title=f"BDF Get Collection sync failed: {docname}")
		frappe.db.set_value(DOCTYPE, docname, "sync_status", "Failed", update_modified=False)
		frappe.db.commit()
	finally:
		publish(docname, done=True)


def sync_collection(docname, only_warehouses=None):
	doc = frappe.get_doc(DOCTYPE, docname)
	doc.ensure_warehouses()
	shift_label = SHIFT_LABEL.get(doc.shift)
	if not shift_label:
		frappe.throw(_("Shift must be M or E."))
	date = getdate(doc.date)

	warehouses = [
		row.warehouse for row in doc.warehouses if not only_warehouses or row.warehouse in only_warehouses
	]
	if not warehouses:
		frappe.throw(_("No warehouses to sync."))

	mpp_codes = dict(
		frappe.get_all(
			"Warehouse",
			filters={"name": ["in", warehouses]},
			fields=["name", "custom_mpp_code"],
			as_list=True,
		)
	)
	existing = get_existing_entries(date, shift_label, warehouses)

	results = {}
	to_fetch = []
	for wh in warehouses:
		res = results[wh] = {
			"mpp_code": cint(mpp_codes.get(wh)),
			"added_last_sync": 0,
			"last_synced_on": now_datetime(),
		}
		if existing[wh]["submitted"]:
			res["status"] = "Submitted"
			res["remarks"] = _("{0} Milk Entries are submitted, so Retry is locked for this warehouse.").format(
				existing[wh]["submitted"]
			)
		elif not res["mpp_code"]:
			res["status"] = "Failed"
			res["remarks"] = _("MPP Code is not set on the Warehouse.")
		else:
			to_fetch.append(wh)

	if to_fetch:
		fetched = fetch_all(doc, [(wh, results[wh]["mpp_code"]) for wh in to_fetch], date)
		supplier_lookup = get_supplier_lookup()
		for i, wh in enumerate(to_fetch, 1):
			publish(docname, progress=i, total=len(to_fetch), warehouse=wh)
			rows, error = fetched[wh]
			if error:
				results[wh].update(status="Failed", remarks=error)
				continue
			results[wh].update(
				create_missing_entries(
					wh, results[wh]["mpp_code"], date, shift_label, rows, existing[wh]["keys"], supplier_lookup
				)
			)
			frappe.db.commit()

	final = get_existing_entries(date, shift_label, warehouses)
	for wh, res in results.items():
		res["entries"] = final[wh]["count"]
		if res.get("status"):
			continue
		if res["not_created"]:
			res["status"] = "Needs Attention"
		elif not res["api_rows"] and not res["entries"]:
			res["status"] = "No Data"
		else:
			res["status"] = "Synced"
			if not res["api_rows"]:
				res["remarks"] = _("API returned no rows this time; existing entries were kept.")

	# Re-read so a save made on the form during the sync is not overwritten.
	doc = frappe.get_doc(DOCTYPE, docname)
	doc.ensure_warehouses()
	for row in doc.warehouses:
		if row.warehouse in results:
			row.update(results[row.warehouse])
	doc.last_synced_on = now_datetime()
	doc.sync_status = get_overall_status(doc.warehouses)
	doc.save(ignore_permissions=True)
	frappe.db.commit()


def get_overall_status(rows):
	statuses = {row.status or "Pending" for row in rows}
	if statuses == {"Failed"}:
		return "Failed"
	if statuses & {"Failed", "Needs Attention", "Pending"}:
		return "Needs Attention"
	return "Synced"


def publish(docname, **message):
	frappe.publish_realtime(SYNC_EVENT, {"name": docname, **message}, doctype=DOCTYPE, docname=docname)


# ---------------------------------------------------------------------- #
# API
# ---------------------------------------------------------------------- #
def fetch_all(doc, targets, date):
	"""One token, then one API call per warehouse, all in parallel. Returns {warehouse: (rows, error)}."""
	token, error = get_token(doc)
	if error:
		return {wh: (None, error) for wh, mpp_code in targets}

	url = (doc.getdata_api_url or "").strip()
	date_str = date.strftime("%d-%m-%Y")
	shift = doc.shift

	def fetch(target):
		wh, mpp_code = target
		return wh, fetch_collection(url, token, mpp_code, date_str, shift)

	with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_CALLS, len(targets))) as pool:
		return dict(pool.map(fetch, targets))


def get_token(doc):
	try:
		resp = requests.post(
			(doc.token_api_url or "").strip(),
			json={"userName": doc.user_name, "password": doc.password},
			headers={"Accept": "*/*", "User-Agent": "BDF", "Content-Type": "application/json"},
			timeout=60,
		)
		resp.raise_for_status()
		token = resp.json().get("Data")
	except (requests.exceptions.RequestException, ValueError, AttributeError) as e:
		return None, _("Token API error: {0}").format(e)
	if not token:
		return None, _("Token not found in the API response.")
	return token, None


def fetch_collection(url, token, mpp_code, date_str, shift):
	"""Runs in a worker thread, so plain HTTP only and no frappe calls. Returns (rows, error)."""
	try:
		resp = requests.post(
			url,
			json={"MPP_Code": mpp_code, "Transaction_Date": date_str, "Shift": shift},
			headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
			timeout=90,
		)
		resp.raise_for_status()
		body = resp.json()
	except requests.exceptions.RequestException as e:
		return None, f"Data API error: {e}"
	except ValueError:
		return None, "Data API returned invalid JSON."

	raw = body.get("Data") if isinstance(body, dict) else None
	if raw in (None, ""):
		return [], None
	if isinstance(raw, str):
		try:
			raw = json.loads(raw)
		except ValueError:
			return None, "Data API 'Data' field is not valid JSON."
	if not isinstance(raw, list):
		return None, "Data API returned an unexpected format."
	return raw, None


# ---------------------------------------------------------------------- #
# Milk Entry creation
# ---------------------------------------------------------------------- #
def get_existing_entries(date, shift_label, warehouses):
	"""Non-cancelled Milk Entries per warehouse for one date + shift, in one query."""
	out = {wh: {"keys": set(), "count": 0, "submitted": 0} for wh in warehouses}
	for me in frappe.get_all(
		"Milk Entry",
		filters={"date": date, "shift": shift_label, "dcs_id": ["in", warehouses], "docstatus": ["<", 2]},
		fields=["dcs_id", "member", "milk_type", "docstatus"],
	):
		info = out.get(me.dcs_id)
		if not info:
			continue
		info["keys"].add((me.member, me.milk_type))
		info["count"] += 1
		info["submitted"] += me.docstatus == 1
	return out


def get_supplier_lookup():
	"""Member codes repeat across DCS (e.g. 101 exists in two DCS), so match on DCS + member code,
	falling back to the one supplier with that code and no DCS."""
	by_dcs, no_dcs = {}, {}
	for s in frappe.get_all(
		"Supplier",
		filters={"custom_member_code": ["is", "set"]},
		fields=["name", "custom_member_code", "dcs_id"],
		order_by="disabled desc",  # enabled suppliers come last and win
	):
		code = normalise_member_code(s.custom_member_code)
		if not code:
			continue
		if s.dcs_id:
			by_dcs[(s.dcs_id, code)] = s.name
		else:
			no_dcs.setdefault(code, []).append(s.name)

	def lookup(warehouse, code):
		if (warehouse, code) in by_dcs:
			return by_dcs[(warehouse, code)]
		names = no_dcs.get(code, [])
		return names[0] if len(names) == 1 else None

	return lookup


def normalise_member_code(value):
	try:
		return str(int(float(value)))
	except (TypeError, ValueError):
		return None


def create_missing_entries(warehouse, mpp_code, date, shift_label, rows, existing_keys, supplier_lookup):
	"""Insert the API rows that are not in ERP yet. Existing entries are never touched."""
	added = 0
	problems = {}

	def skip(reason, entry):
		problems.setdefault(reason, []).append(cstr(entry.get("Member_Code")) or "?")

	for entry in rows:
		if not isinstance(entry, dict) or any(entry.get(k) in (None, "") for k in REQUIRED_KEYS):
			skip(_("Incomplete row from API"), entry if isinstance(entry, dict) else {})
			continue
		code = normalise_member_code(entry.get("Member_Code"))
		member = code and supplier_lookup(warehouse, code)
		if not member:
			skip(_("Member code not mapped to a Supplier of this DCS"), entry)
			continue
		milk_type = MILK_TYPE_MAP.get(entry.get("Milk_Type"), "Mix")
		if (member, milk_type) in existing_keys:
			continue

		frappe.db.savepoint("bgc_milk_entry")
		try:
			make_milk_entry(warehouse, mpp_code, date, shift_label, member, milk_type, entry).insert(
				ignore_permissions=True
			)
		except Exception as e:
			frappe.db.rollback(save_point="bgc_milk_entry")
			frappe.clear_messages()
			skip(error_message(e), entry)
			continue
		existing_keys.add((member, milk_type))
		added += 1

	return {
		"api_rows": len(rows),
		"added_last_sync": added,
		"not_created": sum(len(codes) for codes in problems.values()),
		"remarks": format_problems(problems),
	}


def make_milk_entry(warehouse, mpp_code, date, shift_label, member, milk_type, entry):
	return frappe.get_doc(
		{
			"doctype": "Milk Entry",
			"mpp_code": mpp_code,
			"dcs_id": warehouse,
			"member": member,
			"milk_type": milk_type,
			"shift": shift_label,
			"date": date,
			"volume": entry.get("Qty_KG"),
			"fat": entry.get("Fat"),
			"snf": entry.get("Snf"),
			"clr": entry.get("CLR"),
			"unit_price": entry.get("Rate"),
			"unit_price_with_incentive": entry.get("Rate"),
			"total": entry.get("Amount"),
			"rate_chart_amount": entry.get("Amount"),
		}
	)


def error_message(e):
	return (strip_html_tags(cstr(e)).strip() or e.__class__.__name__)[:140]


def format_problems(problems):
	lines = []
	for reason, codes in list(problems.items())[:10]:
		shown = ", ".join(codes[:15]) + (" …" if len(codes) > 15 else "")
		lines.append(f"{len(codes)} × {reason} (member codes: {shown})")
	return "\n".join(lines)
