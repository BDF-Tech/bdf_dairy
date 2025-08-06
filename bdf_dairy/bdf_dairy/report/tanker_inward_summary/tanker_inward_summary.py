import frappe

def execute(filters=None):
    # Ensure filters are provided and contain required date range fields
    if not filters or not filters.get('from_date') or not filters.get('to_date'):
        frappe.throw("Please provide 'from_date' and 'to_date' filters.")

    # Define columns and data structure for report
    columns = get_columns()
    data = []

    # Fetch acknowledgment data based on filters
    ack_data = get_ack_data(filters)

    # Process each acknowledgment entry
    for ack in ack_data:
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
    ]
def get_ack_data(filters):
    query = """
        SELECT
            ti.name AS id,
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

    if filters.get('dcs'):
        query += " AND ti.dcs IN %s"
        parameters.append(tuple(filters.get('dcs')))

    query += " GROUP BY ti.dcs, ti.name"

    data = frappe.db.sql(query, tuple(parameters), as_dict=True)

    positive_total = {
        "id": "Positive Total",
        "diff_liter": 0,
        "diff_kg": 0,
        "diff_fat": 0,
        "diff_snf": 0,
        "diff_kg_fat": 0,
        "diff_kg_snf": 0,
    }

    negative_total = {
        "id": "Negative Total",
        "diff_liter": 0,
        "diff_kg": 0,
        "diff_fat": 0,
        "diff_snf": 0,
        "diff_kg_fat": 0,
        "diff_kg_snf": 0,
    }
    total = {
        "id": "Total",
        "diff_liter": 0,
        "diff_kg": 0,
        "diff_fat": 0,
        "diff_snf": 0,
        "diff_kg_fat": 0,
        "diff_kg_snf": 0,
    }
    count = 0
    avg_fields = ["diff_fat", "diff_snf", "diff_kg_fat", "diff_kg_snf"]
    for row in data:
        for key in ["diff_liter", "diff_kg", "diff_fat", "diff_snf", "diff_kg_fat", "diff_kg_snf"]:
            value = row.get(key) or 0
            if value >= 0:
                positive_total[key] += value
            else:
                negative_total[key] += value
            if key in avg_fields:
                total[key] += value
        count += 1
    total["diff_fat"] = total["diff_fat"]/count
    total["diff_snf"] = total["diff_snf"]/count
    total["diff_kg_fat"] = total["diff_kg_fat"]/count
    total["diff_kg_snf"] = total["diff_kg_snf"]/count
    data.append(positive_total)
    data.append(negative_total)
    data.append(total)

    return data

def format_diff(value):
    # Format the difference value with color coding based on positivity or negativity
    color = "green" if value >= 0 else "red"
    return f'<span style="color:{color}">{round(value, 2)}</span>'

# def get_ack_data(filters):
#     # Construct SQL query to retrieve acknowledgment data within specified date range
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

#     # Filter by DCS if specified in filters
#     if filters.get('dcs'):
#         query += " AND ti.dcs IN %s"
#         parameters.append(tuple(filters.get('dcs')))

#     # Group by DCS and Tanker Inward ID for distinct results
#     query += " GROUP BY ti.dcs, ti.name"

#     # Execute query and return results as dictionary list
#     return frappe.db.sql(query, tuple(parameters), as_dict=True)


