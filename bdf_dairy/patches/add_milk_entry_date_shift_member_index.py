import frappe


def execute():
	"""Milk Entry duplicate checks (dairy validate + "DCS Validation" server script) filter on
	date + shift + member. Without an index each check scans the whole table (~0.8 s per insert)."""
	frappe.db.add_index("Milk Entry", ["date", "shift", "member"], "date_shift_member_index")
