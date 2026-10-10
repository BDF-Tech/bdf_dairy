import frappe


def execute(filters=None):
    filters = filters or {}
    columns = get_columns(filters)
    data = get_data(filters)
    return columns, data


def get_columns(filters):
    cols = [
        {
            "fieldname": "report_type",
            "label": "Type",
            "fieldtype": "Data",
            "width": 80,
        },
        {
            "fieldname": "department",
            "label": "Department",
            "fieldtype": "Link",
            "options": "Department",
            "width": 160,
        },
        {
            "fieldname": "department_head",
            "label": "Department Head",
            "fieldtype": "Data",
            "width": 140,
        },
        {
            "fieldname": "period",
            "label": "Period",
            "fieldtype": "Data",
            "width": 140,
        },
        {
            "fieldname": "completed_count",
            "label": "Completed",
            "fieldtype": "Int",
            "width": 90,
        },
        {
            "fieldname": "ongoing_count",
            "label": "Ongoing",
            "fieldtype": "Int",
            "width": 80,
        },
        {
            "fieldname": "pending_count",
            "label": "Pending",
            "fieldtype": "Int",
            "width": 80,
        },
        {
            "fieldname": "submitted_to_md",
            "label": "Sent to MD",
            "fieldtype": "Check",
            "width": 90,
        },
        {
            "fieldname": "md_notified_at",
            "label": "MD Notified At",
            "fieldtype": "Datetime",
            "width": 150,
        },
        {
            "fieldname": "name",
            "label": "Report",
            "fieldtype": "Link",
            "options": "Department Report",
            "width": 180,
        },
    ]
    return cols


def get_data(filters):
    report_type = filters.get("report_type", "")
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    department = filters.get("department")
    submitted_to_md = filters.get("submitted_to_md")

    conditions = ["dr.docstatus != 2"]

    if report_type:
        conditions.append(f"dr.report_type = '{frappe.db.escape(report_type)}'")

    if report_type == "Daily" or not report_type:
        if from_date:
            conditions.append(f"(dr.report_date >= '{from_date}' OR dr.report_type != 'Daily')")
        if to_date:
            conditions.append(f"(dr.report_date <= '{to_date}' OR dr.report_type != 'Daily')")

    if department:
        conditions.append(f"dr.department = '{frappe.db.escape(department)}'")

    if submitted_to_md:
        conditions.append("dr.submitted_to_md = 1")

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    reports = frappe.db.sql(
        f"""
        SELECT
            dr.name,
            dr.report_type,
            dr.department,
            dr.department_head,
            dr.report_date,
            dr.week_start_date,
            dr.week_end_date,
            dr.report_month,
            dr.report_year,
            dr.submitted_to_md,
            dr.md_notified_at
        FROM `tabDepartment Report` dr
        WHERE {where_clause}
        ORDER BY dr.modified DESC
        LIMIT 500
        """,
        as_dict=True,
    )

    data = []
    for r in reports:
        completed_count = frappe.db.count(
            "Department Report Work Item",
            {"parent": r.name, "parentfield": "completed_items"},
        )
        ongoing_count = frappe.db.count(
            "Department Report Work Item",
            {"parent": r.name, "parentfield": "ongoing_items"},
        )
        pending_count = frappe.db.count(
            "Department Report Work Item",
            {"parent": r.name, "parentfield": "pending_items"},
        )

        period = ""
        if r.report_type == "Daily":
            period = str(r.report_date or "")
        elif r.report_type == "Weekly":
            period = f"{r.week_start_date} to {r.week_end_date}" if r.week_start_date else ""
        elif r.report_type == "Monthly":
            period = f"{r.report_month} {r.report_year}" if r.report_month else ""

        data.append(
            {
                "name": r.name,
                "report_type": r.report_type,
                "department": r.department,
                "department_head": r.department_head,
                "period": period,
                "completed_count": completed_count,
                "ongoing_count": ongoing_count,
                "pending_count": pending_count,
                "submitted_to_md": r.submitted_to_md,
                "md_notified_at": r.md_notified_at,
            }
        )

    return data
