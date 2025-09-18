# Copyright (c) 2025, BDF and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": "Supplier", "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 150},
        {"label": "DCS", "fieldname": "dcs", "fieldtype": "Link", "options": "Warehouse", "width": 120},
        {"label": "Shift", "fieldname": "shift", "fieldtype": "Data", "width": 100},
        {"label": "Date", "fieldname": "purchase_date", "fieldtype": "Date", "width": 120},
        {"label": "Item", "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 150},
        {"label": "Qty (Ltr)", "fieldname": "quantity", "fieldtype": "Float", "width": 100},
        {"label": "Qty (Kg)", "fieldname": "quantity_kg", "fieldtype": "Float", "width": 100},
        {"label": "FAT", "fieldname": "fat", "fieldtype": "Float", "width": 80},
        {"label": "SNF", "fieldname": "snf", "fieldtype": "Float", "width": 80},
        {"label": "KG FAT", "fieldname": "kg_fat", "fieldtype": "Float", "width": 100},
        {"label": "KG SNF", "fieldname": "kg_snf", "fieldtype": "Float", "width": 100},
        {"label": "Rate", "fieldname": "rate", "fieldtype": "Currency", "width": 80},
        {"label": "Amount", "fieldname": "amount", "fieldtype": "Currency", "width": 100},
    ]


def get_data(filters):
    conditions = []

    if filters.get("company"):
        conditions.append("tp.company = %(company)s")

    if filters.get("shift"):
        conditions.append("tp.shift = %(shift)s")

    if filters.get("from_date"):
        conditions.append("tp.purchase_date >= %(from_date)s")

    if filters.get("to_date"):
        conditions.append("tp.purchase_date <= %(to_date)s")

    if filters.get("supplier"):
        conditions.append("tp.supplier IN %(supplier)s")

    if filters.get("dcs"):
        conditions.append("tp.dcs IN %(dcs)s")

    condition_str = " AND ".join(conditions)

    return frappe.db.sql(f"""
        SELECT
            tp.supplier,
            tp.dcs,
            tp.shift,
            tp.purchase_date,
            tpd.item,
            tpd.quantity,
            tpd.quantity_kg,
            tpd.fat,
            tpd.snf,
            tpd.kg_fat,
            tpd.kg_snf,
            tpd.rate,
            tpd.amount
        FROM `tabTanker Purchase` tp
        JOIN `tabTanker Purchase Details` tpd ON tp.name = tpd.parent
        WHERE tp.docstatus = 1
        {f"AND {condition_str}" if condition_str else ""}
        ORDER BY tp.purchase_date DESC, tp.supplier
    """, {
        "company": filters.get("company"),
        "shift": filters.get("shift"),
        "from_date": filters.get("from_date"),
        "to_date": filters.get("to_date"),
        "supplier": tuple(filters.get("supplier")) if filters.get("supplier") else [],
        "dcs": tuple(filters.get("dcs")) if filters.get("dcs") else []
    }, as_dict=True)

