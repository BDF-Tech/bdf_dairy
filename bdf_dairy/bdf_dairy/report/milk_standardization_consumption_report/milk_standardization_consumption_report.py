# Copyright (c) 2025, BDF and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns, data = [], []
	columns = get_columns(filters)
	data = get_data(filters)
	return columns, data


def get_columns(filters):
	return [
		{
			"label":"Milk Standardization Id",
			"fieldname": "name", 
			"fieldtype": "Link",
			"options": "Milk Standardization",
			"width": 120
		},
		{
			"label":"DMC",
			"fieldname": "dmc", 
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 200
		},
		{
			"label":"Item Code",
			"fieldname": "finished_item", 
			"fieldtype": "Link",
			"options": "Item",
			"width": 120
		},
		{
			"label":"Item Name",
			"fieldname": "finished_item_name", 
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label":"Milk Ltr",
			"fieldname": "milk_ltr", 
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label":"Milk KG",
			"fieldname": "milk_kg", 
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label":"Item Code",
			"fieldname": "child_item_code", 
			"fieldtype": "Link",
			"options": "Item",
			"width": 120
		},
		{
			"label":"Item Name",
			"fieldname": "child_item_name", 
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label":"Actual Qty",
			"fieldname": "actual_quantity", 
			"fieldtype": "Data",
			"width": 120
		},
		
	]


# def get_data(filters):

# 	data = []
# 	all_data = frappe.get_all("Milk Standardization", fields=["name", "dmc", "finished_item", "finished_item_name", "milk_ltr", "milk_kg"])

# 	for row in all_data:

# 		child_items = frappe.get_all(
# 			"Milk Standardization Calculation",
# 			filters={"parent": row.name},
# 			fields=["item_code", "item_name", "available_qty"]
# 		)

# 		if child_items:
# 			for child in child_items:
# 				data.append({
# 					"dmc": row.dmc,
# 					"name": row.name,
# 					"finished_item": row.finished_item,
# 					"finished_item_name": row.finished_item_name,
# 					"milk_ltr": row.milk_ltr,
# 					"milk_kg": row.milk_kg,
# 					"child_item_code": child.item_code,
# 					"child_item_name": child.item_name,
# 					"child_available_qty": child.available_qty
# 				})
# 	return data

	# frappe.throw(str(all_data))

import frappe

def get_data(filters):
    data = []

    conditions = {"docstatus": 1}

    if filters.get("name"):
        conditions["name"] = filters.get("name")

    if filters.get("finished_item_name"):
        conditions["finished_item"] = filters.get("finished_item_name")

    if filters.get("from_date") and filters.get("to_date"):
        conditions["date"] = ["between", [filters.get("from_date"), filters.get("to_date")]]

    all_data = frappe.get_all(
        "Milk Standardization",
        filters=conditions,
        fields=["name", "dmc", "finished_item", "finished_item_name", "milk_ltr", "milk_kg"]
    )

    for row in all_data:
        child_items = frappe.get_all(
            "Milk Standardization Calculation",
            filters={"parent": row.name, "required_item": 1},
            fields=["item_code", "item_name", "actual_quantity"]
        )

        # Flag to show parent fields only once
        parent_shown = False

        if child_items:
            for child in child_items:
                data.append({
                    "dmc": row.dmc if not parent_shown else "",
                    "name": row.name if not parent_shown else "",
                    "finished_item": row.finished_item if not parent_shown else "",
                    "finished_item_name": row.finished_item_name if not parent_shown else "",
                    "milk_ltr": row.milk_ltr if not parent_shown else "",
                    "milk_kg": row.milk_kg if not parent_shown else "",
                    "child_item_code": child.item_code,
                    "child_item_name": child.item_name,
                    "actual_quantity": child.actual_quantity
                })
                parent_shown = True  # Set flag after first child
        else:
            # If no child, still show parent row
            data.append({
                "dmc": row.dmc,
                "name": row.name,
                "finished_item": row.finished_item,
                "finished_item_name": row.finished_item_name,
                "milk_ltr": row.milk_ltr,
                "milk_kg": row.milk_kg,
                "child_item_code": "",
                "child_item_name": "",
                "actual_quantity": ""
            })

    return data
