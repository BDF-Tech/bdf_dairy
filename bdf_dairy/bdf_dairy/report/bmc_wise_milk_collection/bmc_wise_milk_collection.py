# Copyright (c) 2025, BDF and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data

def get_data(filters):
	if not filters:
		filters = {}

	conditions = []
	from_date = filters.get("from_date")
	to_date = filters.get("to_date")
	shift = filters.get("shift")
	dcs = filters.get("dcs")
	member = filters.get("member")

	if shift:
		conditions.append(f"AND m.shift = '{shift}'")

	if dcs:
		dcs_list = ', '.join([f"'{dcs_item}'" for dcs_item in dcs])
		conditions.append(f"AND m.dcs_id in ({dcs_list})")
  
	if member:
		member_list = ', '.join([f"'{member_item}'" for member_item in member])
		conditions.append(f"AND m.member in ({member_list})")


	where_clause = ""
	if conditions:
		where_clause = " ".join(conditions)
	query = f"""
		SELECT 
			m.dcs_id as dcs, 
			m.date, 
			m.member, s.supplier_name as member_name,
			m.shift, 
			SUM(m.volume) as qty, 
			SUM(m.volume) * 1.003 as qty_kg, 
			AVG(m.fat) as fat, 
			AVG(m.snf) as snf, 
			SUM(m.fat_kg) as kg_fat, 
			SUM(m.snf_kg) as kg_snf
		FROM 
			`tabMilk Entry` as m
		LEFT JOIN 
     		`tabSupplier` s on m.member = s.name
		WHERE 
			m.docstatus = 1 
			AND m.date BETWEEN '{from_date}' AND '{to_date}'
			{where_clause}
		GROUP BY 
			m.dcs_id, m.date, m.member, m.shift
	"""
	data = frappe.db.sql(query, as_dict=True)
	return data


def get_columns():
	return [
		{"label": "Date", "fieldname": "date", "fieldtype": "Date", "width": 120},
		{"label": "DCS", "fieldname": "dcs", "fieldtype": "Link", "options": "Warehouse", "width": 120},
		{"label": "Farmer", "fieldname": "member", "fieldtype": "Link", "options": "Supplier","width": 120},
		{"label": "Farmer Name", "fieldname": "member_name", "fieldtype": "Data", "width": 120},
		{"label": "Shift", "fieldname": "shift", "fieldtype": "Data", "width": 120},
		{"label": "Qty (LITER)", "fieldname": "qty", "fieldtype": "Float", "width": 120},
		{"label": "Qty (KG)", "fieldname": "qty_kg", "fieldtype": "Float", "width": 120},
		{"label": "FAT", "fieldname": "fat", "fieldtype": "Float", "width": 120},
		{"label": "SNF", "fieldname": "snf", "fieldtype": "Float", "width": 120},
		{"label": "KG FAT", "fieldname": "kg_fat", "fieldtype": "Float", "width": 120},
		{"label": "KG SNF", "fieldname": "kg_snf", "fieldtype": "Float", "width": 120},
	]
