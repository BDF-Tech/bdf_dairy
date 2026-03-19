import frappe

def execute(filters=None):
    if not filters or not filters.get('from_date') or not filters.get('to_date'):
        frappe.throw("Please provide 'from_date' and 'to_date' filters.")

    columns = get_columns()
    data = []
    pos_tot_kg_fat_amt, neg_tot_kg_fat_amt, pos_tot_kg_snf_amt, neg_tot_kg_snf_amt = 0,0,0,0
    ack_data = get_ack_data(filters)
    for ack in ack_data:
        rate = frappe.db.sql("""
            SELECT 
                mr.snf_rate_in_kg, 
                mr.fat_rate_in_kg
            FROM `tabMilk Rate` mr
            LEFT JOIN `tabWarehouse Child` wc 
                ON wc.parent = mr.name
            WHERE mr.effective_date <= %s AND mr.simplified_milk_rate = 1
            AND wc.warehouse_id = %s
            ORDER BY mr.effective_date DESC 
            LIMIT 1
        """, (ack.get("date"), ack.get("dcs")), as_dict=True)

        if rate:
            fat_rate = rate[0].get('fat_rate_in_kg')
            snf_rate = rate[0].get('snf_rate_in_kg')
            kg_fat_amount = round((round(ack.get('diff_kg_fat', 0) or 0, 3) * fat_rate), 2)
            kg_snf_amount = round((round(ack.get('diff_kg_snf', 0) or 0, 3) * snf_rate), 2)
            if kg_fat_amount > 0:
                pos_tot_kg_fat_amt += kg_fat_amount
            else:
                neg_tot_kg_fat_amt += kg_fat_amount
            
            if kg_snf_amount > 0:
                pos_tot_kg_snf_amt += kg_snf_amount
            else:
                neg_tot_kg_snf_amt += kg_snf_amount
        else:
            if ack.get('id') == "Positive Total":
                kg_fat_amount = pos_tot_kg_fat_amt
                kg_snf_amount = pos_tot_kg_snf_amt
            elif ack.get('id') == "Negative Total":
                kg_fat_amount = neg_tot_kg_fat_amt
                kg_snf_amount = neg_tot_kg_snf_amt
            elif ack.get('id') == "Total":
                kg_fat_amount = pos_tot_kg_fat_amt + neg_tot_kg_fat_amt
                kg_snf_amount = pos_tot_kg_snf_amt + neg_tot_kg_snf_amt
            else:
                kg_fat_amount = kg_snf_amount = 0
                                              
        data.append({
            "id": ack.get('id'),
            "date": ack.get('date'),
            "dcs": ack.get('dcs'),
            "ack_liter": ack.get('ack_liter', 0),
            "ack_kg": ack.get('ack_kg', 0),
            "ack_fat": ack.get('ack_fat', 0),
            "ack_snf": ack.get('ack_snf', 0),
            "ack_kg_fat": ack.get('ack_kg_fat', 0),
            "ack_kg_snf": ack.get('ack_kg_snf', 0),
            "diff_liter": format_diff(round(ack.get('diff_liter', 0) or 0, 3)),
            "diff_kg": format_diff(round(ack.get('diff_kg', 0) or 0, 3)),
            "diff_fat": format_diff(round(ack.get('diff_fat', 0) or 0, 3)),
            "diff_snf": format_diff(round(ack.get('diff_snf', 0) or 0, 3)),
            "diff_kg_fat": format_diff(round(ack.get('diff_kg_fat', 0) or 0, 3)),
            "diff_kg_snf": format_diff(round(ack.get('diff_kg_snf', 0) or 0, 3)),
            "kg_fat_amount": format_diff(kg_fat_amount),
            "kg_snf_amount": format_diff(kg_snf_amount),
        })

    return columns, data

def get_columns():
    return [
        {"label": "ID", "fieldname": "id", "fieldtype": "Link", "options": "Tanker Inward", "width": 120},
        {"label": "Date", "fieldname": "date", "fieldtype": "Date", "width": 120},
        {"label": "DCS", "fieldname": "dcs", "fieldtype": "Link", "options": "Warehouse", "width": 120},
        {"label": "ACK LITER", "fieldname": "ack_liter", "fieldtype": "Float", "width": 120, 'precision': 2},
        {"label": "ACK KG", "fieldname": "ack_kg", "fieldtype": "Float", "width": 120,'precision': 2},
        {"label": "ACK FAT", "fieldname": "ack_fat", "fieldtype": "Float", "width": 120,'precision': 2},
        {"label": "ACK SNF", "fieldname": "ack_snf", "fieldtype": "Float", "width": 120,'precision': 2},
        {"label": "ACK KG FAT", "fieldname": "ack_kg_fat", "fieldtype": "Float", "width": 120,'precision': 2},
        {"label": "ACK KG SNF", "fieldname": "ack_kg_snf", "fieldtype": "Float", "width": 120,'precision': 2},
        {"label": "DIFF LITER", "fieldname": "diff_liter", "fieldtype": "Data", "width": 120,'precision': 2},
        {"label": "DIFF KG", "fieldname": "diff_kg", "fieldtype": "Data", "width": 120,'precision': 2},
        {"label": "DIFF FAT", "fieldname": "diff_fat", "fieldtype": "Data", "width": 120,'precision': 2},
        {"label": "DIFF SNF", "fieldname": "diff_snf", "fieldtype": "Data", "width": 120,'precision': 2},
        {"label": "DIFF KG FAT", "fieldname": "diff_kg_fat", "fieldtype": "Data", "width": 120,'precision': 2},
        {"label": "DIFF KG SNF", "fieldname": "diff_kg_snf", "fieldtype": "Data", "width": 120,'precision': 2},
        {"label": "KG FAT AMOUNT", "fieldname": "kg_fat_amount", "fieldtype": "Data", "width": 120,'precision': 2},
        {"label": "KG SNF AMOUNT", "fieldname": "kg_snf_amount", "fieldtype":"Data", "width":120, 'precision':2}
    ]

def get_ack_data(filters):
    query = """
        SELECT
            ti.name AS id,
            ti.name AS tanker_inward,
            ti.tanker_inward_date AS date,
            ti.dcs,
            SUM(mrt.qty_in_liter) AS ack_liter,
            SUM(mrt.qty_in_kg) AS ack_kg,
            AVG(mrt.fat) AS ack_fat,
            AVG(mrt.snf) AS ack_snf,
            SUM(mrt.kg_fat) AS ack_kg_fat,
            SUM(mrt.kg_snf) AS ack_kg_snf,
            SUM(d.qty_in_liter) AS diff_liter,
            SUM(d.qty_in_kg) AS diff_kg,
            AVG(d.fat) AS diff_fat,
            AVG(d.snf) AS diff_snf,
            SUM(d.kg_fat) AS diff_kg_fat,
            SUM(d.kg_snf) AS diff_kg_snf
        FROM 
            `tabTanker Inward` AS ti
        LEFT JOIN 
            `tabMilk Received From Tanker` AS mrt ON mrt.parent = ti.name
        LEFT JOIN 
            `tabDifference of DCS and Tanker Milk Received` AS d ON d.parent = ti.name
        WHERE 
            ti.tanker_inward_date BETWEEN %s AND %s
            AND ti.docstatus = 1
    """

    parameters = [filters.get('from_date'), filters.get('to_date')]

    # ✅ Apply checkbox filter dynamically
    if filters.get("cp_collection") is not None:
        query += " AND ti.cp_collection = %s"
        parameters.append(filters.get("cp_collection"))

    if filters.get('dcs'):
        query += " AND ti.dcs IN %s"
        parameters.append(tuple(filters.get('dcs')))

    query += " GROUP BY ti.dcs, ti.name"

    data = frappe.db.sql(query, tuple(parameters), as_dict=True)

    # Totals initialization
    ack_total = {}
    diff_total = {}
    positive_total = {"id": "Positive Total"}
    negative_total = {"id": "Negative Total"}

    # Fields to track
    ack_sum_fields = ["ack_liter", "ack_kg", "ack_kg_fat", "ack_kg_snf",]
    ack_avg_fields = ["ack_fat", "ack_snf"]

    diff_fields = ["diff_liter", "diff_kg", "diff_fat", "diff_snf", "diff_kg_fat", "diff_kg_snf"]
    diff_avg_fields = ["diff_fat", "diff_snf"]

    # Initialize all required keys
    for field in ack_sum_fields + ack_avg_fields:
        ack_total[field] = 0
    for field in diff_fields:
        diff_total[field] = 0
        positive_total[field] = 0
        negative_total[field] = 0

    ack_count = 0
    diff_count = 0

    for row in data:
        # ACK totals
        ack_count += 1
        for field in ack_sum_fields:
            ack_total[field] += row.get(field) or 0
        for field in ack_avg_fields:
            ack_total[field] += row.get(field) or 0

        # DIFF totals
        diff_count += 1
        for field in diff_fields:
            value = row.get(field) or 0
            diff_total[field] += value
            if value >= 0:
                positive_total[field] += value
            else:
                negative_total[field] += value

    # Average calculations
    if ack_count > 0:
        for field in ack_avg_fields:
            ack_total[field] = ack_total[field] / ack_count

    if diff_count > 0:
        for field in diff_avg_fields:
            diff_total[field] = diff_total[field] / diff_count

    # Combine ACK + DIFF into one Total row
    combined_total = {"id": "Total"}
    combined_total.update(ack_total)
    combined_total.update(diff_total)

    # Append summary rows
    data.append(positive_total)
    data.append(negative_total)
    data.append(combined_total)

    return data


def format_diff(value):
    # Format the difference value with color coding based on positivity or negativity
    color = "green" if value >= 0 else "red"
    return f'<span style="color:{color}">{round(value, 2)}</span>'









































# import frappe

# def execute(filters=None):
#     if not filters or not filters.get('from_date') or not filters.get('to_date'):
#         frappe.throw("Please provide 'from_date' and 'to_date' filters.")

#     columns = get_columns()
#     data = []

#     ack_data = get_ack_data(filters)
#     for ack in ack_data:
#         data.append({
#             "id": ack.get('id'),
#             "date": ack.get('date'),
#             "dcs": ack.get('dcs'),
#             "ack_liter": ack.get('ack_liter', 0),
#             "ack_kg": ack.get('ack_kg', 0),
#             "ack_fat": ack.get('ack_fat', 0),
#             "ack_snf": ack.get('ack_snf', 0),
#             "ack_kg_fat": ack.get('ack_kg_fat', 0),
#             "ack_kg_snf": ack.get('ack_kg_snf', 0),
#             "diff_liter": format_diff(round(ack.get('diff_liter', 0) or 0, 3)),
#             "diff_kg": format_diff(round(ack.get('diff_kg', 0) or 0, 3)),
#             "diff_fat": format_diff(round(ack.get('diff_fat', 0) or 0, 3)),
#             "diff_snf": format_diff(round(ack.get('diff_snf', 0) or 0, 3)),
#             "diff_kg_fat": format_diff(round(ack.get('diff_kg_fat', 0) or 0, 3)),
#             "diff_kg_snf": format_diff(round(ack.get('diff_kg_snf', 0) or 0, 3)),
#         })

#     return columns, data

# def get_columns():
#     return [
#         {"label": "ID", "fieldname": "id", "fieldtype": "Link", "options": "Tanker Inward", "width": 120},
#         {"label": "Date", "fieldname": "date", "fieldtype": "Date", "width": 120},
#         {"label": "DCS", "fieldname": "dcs", "fieldtype": "Link", "options": "Warehouse", "width": 120},
#         {"label": "ACK LITER", "fieldname": "ack_liter", "fieldtype": "Float", "width": 120, 'precision': 2},
#         {"label": "ACK KG", "fieldname": "ack_kg", "fieldtype": "Float", "width": 120,'precision': 2},
#         {"label": "ACK FAT", "fieldname": "ack_fat", "fieldtype": "Float", "width": 120,'precision': 2},
#         {"label": "ACK SNF", "fieldname": "ack_snf", "fieldtype": "Float", "width": 120,'precision': 2},
#         {"label": "ACK KG FAT", "fieldname": "ack_kg_fat", "fieldtype": "Float", "width": 120,'precision': 2},
#         {"label": "ACK KG SNF", "fieldname": "ack_kg_snf", "fieldtype": "Float", "width": 120,'precision': 2},
#         {"label": "DIFF LITER", "fieldname": "diff_liter", "fieldtype": "Data", "width": 120,'precision': 2},
#         {"label": "DIFF KG", "fieldname": "diff_kg", "fieldtype": "Data", "width": 120,'precision': 2},
#         {"label": "DIFF FAT", "fieldname": "diff_fat", "fieldtype": "Data", "width": 120,'precision': 2},
#         {"label": "DIFF SNF", "fieldname": "diff_snf", "fieldtype": "Data", "width": 120,'precision': 2},
#         {"label": "DIFF KG FAT", "fieldname": "diff_kg_fat", "fieldtype": "Data", "width": 120,'precision': 2},
#         {"label": "DIFF KG SNF", "fieldname": "diff_kg_snf", "fieldtype": "Data", "width": 120,'precision': 2},
#     ]

# def get_ack_data(filters):
#     query = """
#         SELECT
#             ti.name AS id,
#             ti.tanker_inward_date AS date,
#             ti.dcs,
#             SUM(mrt.qty_in_liter) AS ack_liter,
#             SUM(mrt.qty_in_kg) AS ack_kg,
#             AVG(mrt.fat) AS ack_fat,
#             AVG(mrt.snf) AS ack_snf,
#             SUM(mrt.kg_fat) AS ack_kg_fat,
#             SUM(mrt.kg_snf) AS ack_kg_snf,
#             SUM(d.qty_in_liter) AS diff_liter,
#             SUM(d.qty_in_kg) AS diff_kg,
#             AVG(d.fat) AS diff_fat,
#             AVG(d.snf) AS diff_snf,
#             SUM(d.kg_fat) AS diff_kg_fat,
#             SUM(d.kg_snf) AS diff_kg_snf
#         FROM 
#             `tabTanker Inward` AS ti
#         LEFT JOIN 
#             `tabMilk Received From Tanker` AS mrt ON mrt.parent = ti.name
#         LEFT JOIN 
#             `tabDifference of DCS and Tanker Milk Received` AS d ON d.parent = ti.name
#         WHERE 
#             ti.tanker_inward_date BETWEEN %s AND %s
#             AND ti.docstatus = 1
#     """

#     parameters = [filters.get('from_date'), filters.get('to_date')]

#     if filters.get('dcs'):
#         query += " AND ti.dcs IN %s"
#         parameters.append(tuple(filters.get('dcs')))

#     query += " GROUP BY ti.dcs, ti.name"

#     data = frappe.db.sql(query, tuple(parameters), as_dict=True)

#     # Totals initialization
#     ack_total = {}
#     diff_total = {}
#     positive_total = {"id": "Positive Total"}
#     negative_total = {"id": "Negative Total"}

#     # Fields to track
#     ack_sum_fields = ["ack_liter", "ack_kg", "ack_kg_fat", "ack_kg_snf"]
#     ack_avg_fields = ["ack_fat", "ack_snf"]

#     diff_fields = ["diff_liter", "diff_kg", "diff_fat", "diff_snf", "diff_kg_fat", "diff_kg_snf"]
#     diff_avg_fields = ["diff_fat", "diff_snf"]

#     # Initialize all required keys
#     for field in ack_sum_fields + ack_avg_fields:
#         ack_total[field] = 0
#     for field in diff_fields:
#         diff_total[field] = 0
#         positive_total[field] = 0
#         negative_total[field] = 0

#     ack_count = 0
#     diff_count = 0

#     for row in data:
#         # ACK totals
#         ack_count += 1
#         for field in ack_sum_fields:
#             ack_total[field] += row.get(field) or 0
#         for field in ack_avg_fields:
#             ack_total[field] += row.get(field) or 0

#         # DIFF totals
#         diff_count += 1
#         for field in diff_fields:
#             value = row.get(field) or 0
#             diff_total[field] += value
#             if value >= 0:
#                 positive_total[field] += value
#             else:
#                 negative_total[field] += value

#     # Average calculations
#     if ack_count > 0:
#         for field in ack_avg_fields:
#             ack_total[field] = ack_total[field] / ack_count

#     if diff_count > 0:
#         for field in diff_avg_fields:
#             diff_total[field] = diff_total[field] / diff_count

#     # Combine ACK + DIFF into one Total row
#     combined_total = {"id": "Total"}
#     combined_total.update(ack_total)
#     combined_total.update(diff_total)

#     # Append summary rows
#     data.append(positive_total)
#     data.append(negative_total)
#     data.append(combined_total)

#     return data


# def format_diff(value):
#     # Format the difference value with color coding based on positivity or negativity
#     color = "green" if value >= 0 else "red"
#     return f'<span style="color:{color}">{round(value, 2)}</span>'
