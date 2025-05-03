# # Copyright (c) 2025, BDF and contributors
# # For license information, please see license.txt

# import frappe


# def execute(filters=None):
# 	columns = get_columns()
# 	data = get_data(filters)
# 	return columns, data

# def get_data(filters):
# 	if not filters:
# 		filters = {}

# 	conditions = []
# 	from_date = filters.get("from_date")
# 	to_date = filters.get("to_date")
# 	shift = filters.get("shift")
# 	dcs = filters.get("dcs")
# 	member = filters.get("member")

# 	if shift:
# 		conditions.append(f"AND m.shift = '{shift}'")

# 	if dcs:
# 		dcs_list = ', '.join([f"'{dcs_item}'" for dcs_item in dcs])
# 		conditions.append(f"AND m.dcs_id in ({dcs_list})")
  
# 	if member:
# 		member_list = ', '.join([f"'{member_item}'" for member_item in member])
# 		conditions.append(f"AND m.member in ({member_list})")


# 	where_clause = ""
# 	if conditions:
# 		where_clause = " ".join(conditions)
# 	query = f"""
# 		SELECT 
# 			m.dcs_id as dcs, 
# 			m.date, 
# 			m.member, s.supplier_name as member_name,
# 			m.shift, 
# 			SUM(m.volume) as qty, 
# 			SUM(m.volume) * 1.003 as qty_kg, 
# 			AVG(m.fat) as fat, 
# 			AVG(m.snf) as snf, 
# 			SUM(m.fat_kg) as kg_fat, 
# 			SUM(m.snf_kg) as kg_snf
# 		FROM 
# 			`tabMilk Entry` as m
# 		LEFT JOIN 
#      		`tabSupplier` s on m.member = s.name
# 		WHERE 
# 			m.docstatus = 1 
# 			AND m.date BETWEEN '{from_date}' AND '{to_date}'
# 			{where_clause}
# 		GROUP BY 
# 			m.dcs_id, m.date, m.member, m.shift
# 	"""
# 	data = frappe.db.sql(query, as_dict=True)
# 	return data


# def get_columns():
# 	return [
# 		{"label": "Date", "fieldname": "date", "fieldtype": "Date", "width": 120},
# 		{"label": "DCS", "fieldname": "dcs", "fieldtype": "Link", "options": "Warehouse", "width": 120},
# 		{"label": "Farmer", "fieldname": "member", "fieldtype": "Link", "options": "Supplier","width": 120},
# 		{"label": "Farmer Name", "fieldname": "member_name", "fieldtype": "Data", "width": 120},
# 		{"label": "Shift", "fieldname": "shift", "fieldtype": "Data", "width": 120},
# 		{"label": "Qty (LITER)", "fieldname": "qty", "fieldtype": "Float", "width": 120},
# 		{"label": "Qty (KG)", "fieldname": "qty_kg", "fieldtype": "Float", "width": 120},
# 		{"label": "FAT", "fieldname": "fat", "fieldtype": "Float", "width": 120},
# 		{"label": "SNF", "fieldname": "snf", "fieldtype": "Float", "width": 120},
# 		{"label": "KG FAT", "fieldname": "kg_fat", "fieldtype": "Float", "width": 120},
# 		{"label": "KG SNF", "fieldname": "kg_snf", "fieldtype": "Float", "width": 120},
# 	]

# import frappe
# from frappe import _

# def execute(filters=None):
#     columns = get_columns()
#     data = get_data(filters)
#     return columns, data

# def get_data(filters):
#     if not filters:
#         filters = {}

#     # Conditions from the filters
#     from_date = filters.get("from_date")
#     to_date = filters.get("to_date")
#     shift = filters.get("shift")
#     dcs = filters.get("dcs")
#     member = filters.get("member")
#     show_dcs_total = filters.get("dcstotal", 0)

#     query_conditions = {
#         'docstatus': 1,
#         'date': ['between', [from_date, to_date]]
#     }

#     if shift:
#         query_conditions['shift'] = shift

#     if dcs:
#         query_conditions['dcs_id'] = ['in', dcs]

#     if member:
#         if isinstance(member, list):
#             query_conditions['member'] = ['in', member]
#         else:
#             query_conditions['member'] = member

#     # Fetch Milk Entry records using Frappe ORM
#     data = frappe.get_all(
#         'Milk Entry',
#         filters=query_conditions,
#         fields=['dcs_id', 'date', 'member', 'shift', 'volume', 'fat', 'snf', 'fat_kg', 'snf_kg'],
#         order_by="date asc, dcs_id asc, member asc, shift asc"
#     )

#     # Fetch all supplier names once and map them
#     supplier_dict = {supplier.name: supplier.supplier_name for supplier in frappe.get_all('Supplier', fields=['name', 'supplier_name'])}

#     # Initialize variables to store grouped data and totals
#     grouped_data = []
#     dcs_totals = {}  # To store totals per DCS
#     count = 0  # For averaging FAT and SNF

#     if show_dcs_total:
#     # Initialize dictionary to store totals per DCS, Date, and Shift
#         dcs_totals = {} 

#         for row in data:
#             dcs_id = row["dcs_id"]
#             member_name = supplier_dict.get(row["member"], "")
#             date = row["date"]
#             shift = row["shift"]

#             # Initialize DCS totals dictionary if not already present for this DCS
#             if dcs_id not in dcs_totals:
#                 dcs_totals[dcs_id] = {}

#             # Initialize dictionary for each Date and Shift combination
#             if date not in dcs_totals[dcs_id]:
#                 dcs_totals[dcs_id][date] = {}

#             if shift not in dcs_totals[dcs_id][date]:
#                 dcs_totals[dcs_id][date][shift] = {
#                     "qty": 0, "qty_kg": 0, "fat": 0, "snf": 0,
#                     "kg_fat": 0, "kg_snf": 0, "count": 0
#                 }

#             # Accumulate DCS totals for each Date and Shift combination
#             volume = row["volume"]
#             fat = row["fat"]
#             snf = row["snf"]

#             dcs_totals[dcs_id][date][shift]["qty"] += volume
#             dcs_totals[dcs_id][date][shift]["qty_kg"] += volume * 1.003
#             dcs_totals[dcs_id][date][shift]["fat"] += fat
#             dcs_totals[dcs_id][date][shift]["snf"] += snf
#             dcs_totals[dcs_id][date][shift]["kg_fat"] += row["fat_kg"]
#             dcs_totals[dcs_id][date][shift]["kg_snf"] += row["snf_kg"]
#             dcs_totals[dcs_id][date][shift]["count"] += 1

#         # Add DCS totals for each Date and Shift to the grouped data
#         for dcs_id, dates in dcs_totals.items():
#             for date, shifts in dates.items():
#                 for shift, totals in shifts.items():
#                     if totals["count"] > 0:
#                         # Calculate average FAT and SNF for the specific Date and Shift
#                         totals["fat"] = totals["fat"] / totals["count"] if totals["count"] else 0
#                         totals["snf"] = totals["snf"] / totals["count"] if totals["count"] else 0

#                         # Append total row for the DCS, Date, and Shift
#                         grouped_data.append({
#                             "date": date,  # Use the current date for the total row
#                             "dcs": dcs_id,
#                             "member": "",
#                             "member_name": "TOTAL",  # Mark as total row
#                             "shift": shift,  # Use the current shift for the total row
#                             "qty": totals["qty"],
#                             "qty_kg": totals["qty_kg"],
#                             "fat": totals["fat"],
#                             "snf": totals["snf"],
#                             "kg_fat": totals["kg_fat"],
#                             "kg_snf": totals["kg_snf"],
#                             "is_total": 1  # Mark as total row for DCS
#                         })

#     else:
#         # If Show DCS Total is not checked, show individual data (farmer-wise and date-wise)
#         current_date = None
#         daily_totals = {
#             "qty": 0, "qty_kg": 0, "fat": 0, "snf": 0, "kg_fat": 0, "kg_snf": 0,
#             "dcs": "TOTAL", "member": "", "member_name": "", "shift": "",
#             "is_total": 1  # Mark total rows
#         }
#         for row in data:
#             member_name = supplier_dict.get(row["member"], "")

#             if current_date and current_date != row["date"]:
#                 if daily_totals["qty"] > 0:
#                     daily_totals["date"] = current_date
#                     daily_totals["fat"] = daily_totals["fat"] / count if count else 0
#                     daily_totals["snf"] = daily_totals["snf"] / count if count else 0
#                     grouped_data.append(daily_totals.copy())

#                 # Reset daily totals
#                 daily_totals.update({
#                     "qty": 0, "qty_kg": 0, "fat": 0, "snf": 0, "kg_fat": 0, "kg_snf": 0
#                 })
#                 count = 0

#             current_date = row["date"]
#             volume = row["volume"]
#             fat = row["fat"]
#             snf = row["snf"]

#             daily_totals["qty"] += volume
#             daily_totals["qty_kg"] += volume * 1.003
#             daily_totals["fat"] += fat
#             daily_totals["snf"] += snf
#             daily_totals["kg_fat"] += row["fat_kg"]
#             daily_totals["kg_snf"] += row["snf_kg"]
#             count += 1

#             # Add individual farmer data
#             grouped_data.append({
#                 "date": row["date"],
#                 "dcs": row["dcs_id"],
#                 "member": row["member"],
#                 "member_name": member_name,
#                 "shift": row["shift"],
#                 "qty": volume,
#                 "qty_kg": volume * 1.003,
#                 "fat": fat,
#                 "snf": snf,
#                 "kg_fat": row["fat_kg"],
#                 "kg_snf": row["snf_kg"]
#             })

#         if daily_totals["qty"] > 0:
#             daily_totals["date"] = current_date
#             daily_totals["fat"] = daily_totals["fat"] / count if count else 0
#             daily_totals["snf"] = daily_totals["snf"] / count if count else 0
#             grouped_data.append(daily_totals.copy())

#     return grouped_data

# def get_columns():
#     return [
#         {"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 120},
#         {"label": _("DCS"), "fieldname": "dcs", "fieldtype": "Link", "options": "Warehouse", "width": 120},
#         {"label": _("Farmer"), "fieldname": "member", "fieldtype": "Link", "options": "Supplier", "width": 120},
#         {"label": _("Farmer Name"), "fieldname": "member_name", "fieldtype": "Data", "width": 120},
#         {"label": _("Farmer Group"), "fieldname": "member_name", "fieldtype": "Link", "options": "Supplier Group", "width": 120},
#         {"label": _("Shift"), "fieldname": "shift", "fieldtype": "Data", "width": 120},
#         {"label": _("Qty (LITER)"), "fieldname": "qty", "fieldtype": "Float", "width": 120},
#         {"label": _("Qty (KG)"), "fieldname": "qty_kg", "fieldtype": "Float", "width": 120},
#         {"label": _("FAT"), "fieldname": "fat", "fieldtype": "Float", "width": 120},
#         {"label": _("SNF"), "fieldname": "snf", "fieldtype": "Float", "width": 120},
#         {"label": _("KG FAT"), "fieldname": "kg_fat", "fieldtype": "Float", "width": 120},
#         {"label": _("KG SNF"), "fieldname": "kg_snf", "fieldtype": "Float", "width": 120},
#     ]

import frappe
from frappe import _

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_data(filters):
    if not filters:
        filters = {}

    # Extracting the filters
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    shift = filters.get("shift")
    dcs = filters.get("dcs")
    member = filters.get("member")
    member_groups = filters.get("member_group")  # New filter for member_group
    show_dcs_total = filters.get("dcstotal", 0)

    query_conditions = {
        'docstatus': 1,
        'date': ['between', [from_date, to_date]]
    }

    if shift:
        query_conditions['shift'] = shift

    if dcs:
        if isinstance(dcs, list) and len(dcs) > 0:
            query_conditions['dcs_id'] = ['in', dcs]
        elif isinstance(dcs, str):  # single value
            query_conditions['dcs_id'] = dcs

    if member:
        if isinstance(member, list) and len(member) > 0:
            query_conditions['member'] = ['in', member]
        elif isinstance(member, str):  # single value
            query_conditions['member'] = member

    # If member_group filter is applied, get the corresponding members from the Supplier table
    if member_groups:
        supplier_ids = frappe.get_all('Supplier', filters={'supplier_group': ["in", member_groups]}, fields=['name'])
        supplier_names = [supplier['name'] for supplier in supplier_ids]
        query_conditions['member'] = ['in', supplier_names]  # Update the query filter to include only those suppliers

    # Fetch Milk Entry records using Frappe ORM
    data = frappe.get_all(
        'Milk Entry',
        filters=query_conditions,
        fields=['dcs_id', 'date', 'member', 'shift', 'volume', 'fat', 'snf', 'fat_kg', 'snf_kg'],
        order_by="date asc, dcs_id asc, member asc, shift asc"
    )

    # Fetch member_group from the Supplier table once, map them
    suppliers = frappe.get_all('Supplier', fields=['name', 'supplier_group'])
    supplier_group_dict = {supplier.name: supplier.supplier_group for supplier in suppliers}

    # Initialize variables to store grouped data
    grouped_data = []

    if show_dcs_total:
        # Initialize dictionary to store totals per DCS, Date, and Shift
        dcs_totals = {}

        for row in data:
            dcs_id = row["dcs_id"]
            member_name = frappe.get_value("Supplier", row["member"], "supplier_name")
            member_group = supplier_group_dict.get(row["member"], "")  # Get member_group from the supplier
            date = row["date"]
            shift = row["shift"]

            # Initialize DCS totals dictionary if not already present for this DCS
            if dcs_id not in dcs_totals:
                dcs_totals[dcs_id] = {}

            # Initialize dictionary for each Date and Shift combination
            if date not in dcs_totals[dcs_id]:
                dcs_totals[dcs_id][date] = {}

            if shift not in dcs_totals[dcs_id][date]:
                dcs_totals[dcs_id][date][shift] = {
                    "qty": 0, "qty_kg": 0, "fat": 0, "snf": 0,
                    "kg_fat": 0, "kg_snf": 0, "count": 0
                }

            # Accumulate DCS totals for each Date and Shift combination
            volume = row["volume"]
            fat = row["fat"]
            snf = row["snf"]

            dcs_totals[dcs_id][date][shift]["qty"] += volume
            dcs_totals[dcs_id][date][shift]["qty_kg"] += volume * 1.03
            dcs_totals[dcs_id][date][shift]["fat"] += fat
            dcs_totals[dcs_id][date][shift]["snf"] += snf
            dcs_totals[dcs_id][date][shift]["kg_fat"] += row["fat_kg"]
            dcs_totals[dcs_id][date][shift]["kg_snf"] += row["snf_kg"]
            dcs_totals[dcs_id][date][shift]["count"] += 1

        # Add DCS totals for each Date and Shift to the grouped data
        for dcs_id, dates in dcs_totals.items():
            for date, shifts in dates.items():
                for shift, totals in shifts.items():
                    if totals["count"] > 0:
                        # Calculate average FAT and SNF for the specific Date and Shift
                        totals["fat"] = totals["fat"] / totals["count"] if totals["count"] else 0
                        totals["snf"] = totals["snf"] / totals["count"] if totals["count"] else 0

                        # Append total row for the DCS, Date, and Shift
                        grouped_data.append({
                            "date": date,
                            "dcs": dcs_id,
                            "member": "",
                            "member_name": "TOTAL",  # Mark as total row
                            "member_group": "",  # Total row doesn't have a member group
                            "shift": shift,
                            "qty": totals["qty"],
                            "qty_kg": totals["qty_kg"],
                            "fat": totals["fat"],
                            "snf": totals["snf"],
                            "kg_fat": totals["kg_fat"],
                            "kg_snf": totals["kg_snf"],
                            "is_total": 1  # Mark as total row for DCS
                        })

    else:
        # If Show DCS Total is not checked, show individual data (farmer-wise and date-wise)
        current_date = None
        daily_totals = {
            "qty": 0, "qty_kg": 0, "fat": 0, "snf": 0, "kg_fat": 0, "kg_snf": 0,
            "dcs": "TOTAL", "member": "", "member_name": "", "shift": "",
            "is_total": 1  # Mark total rows
        }
        count = 0

        for row in data:
            member_name = frappe.get_value("Supplier", row["member"], "supplier_name")
            member_group = supplier_group_dict.get(row["member"], "")  # Get member_group from the supplier
            
            if current_date and current_date != row["date"]:
                if daily_totals["qty"] > 0:
                    daily_totals["date"] = current_date
                    daily_totals["fat"] = daily_totals["fat"] / count if count else 0
                    daily_totals["snf"] = daily_totals["snf"] / count if count else 0
                    grouped_data.append(daily_totals.copy())

                # Reset daily totals
                daily_totals.update({
                    "qty": 0, "qty_kg": 0, "fat": 0, "snf": 0, "kg_fat": 0, "kg_snf": 0
                })
                count = 0

            current_date = row["date"]
            volume = row["volume"]
            fat = row["fat"]
            snf = row["snf"]

            daily_totals["qty"] += volume
            daily_totals["qty_kg"] += volume * 1.003
            daily_totals["fat"] += fat
            daily_totals["snf"] += snf
            daily_totals["kg_fat"] += row["fat_kg"]
            daily_totals["kg_snf"] += row["snf_kg"]
            count += 1

            # Add individual farmer data
            grouped_data.append({
                "date": row["date"],
                "dcs": row["dcs_id"],
                "member": row["member"],
                "member_name": member_name,
                "member_group": member_group,  # Add member_group here
                "shift": row["shift"],
                "qty": volume,
                "qty_kg": volume * 1.003,
                "fat": fat,
                "snf": snf,
                "kg_fat": row["fat_kg"],
                "kg_snf": row["snf_kg"]
            })

        if daily_totals["qty"] > 0:
            daily_totals["date"] = current_date
            daily_totals["fat"] = daily_totals["fat"] / count if count else 0
            daily_totals["snf"] = daily_totals["snf"] / count if count else 0
            grouped_data.append(daily_totals.copy())

    return grouped_data

def get_columns():
    return [
        {"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 120},
        {"label": _("DCS"), "fieldname": "dcs", "fieldtype": "Link", "options": "Warehouse", "width": 120},
        {"label": _("Farmer"), "fieldname": "member", "fieldtype": "Link", "options": "Supplier", "width": 120},
        {"label": _("Farmer Name"), "fieldname": "member_name", "fieldtype": "Data", "width": 120},
        {"label": _("Farmer Group"), "fieldname": "member_group", "fieldtype": "Link", "options": "Supplier Group", "width": 120},  # New column for Supplier Group
        {"label": _("Shift"), "fieldname": "shift", "fieldtype": "Data", "width": 120},
        {"label": _("Qty (LITER)"), "fieldname": "qty", "fieldtype": "Float", "width": 120},
        {"label": _("Qty (KG)"), "fieldname": "qty_kg", "fieldtype": "Float", "width": 120, "precision": 2},
        {"label": _("FAT"), "fieldname": "fat", "fieldtype": "Float", "width": 120},
        {"label": _("SNF"), "fieldname": "snf", "fieldtype": "Float", "width": 120},
        {"label": _("KG FAT"), "fieldname": "kg_fat", "fieldtype": "Float", "width": 120, "precision": 2},
        {"label": _("KG SNF"), "fieldname": "kg_snf", "fieldtype": "Float", "width": 120, "precision": 2},
    ]

