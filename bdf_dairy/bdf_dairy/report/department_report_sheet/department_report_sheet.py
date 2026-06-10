import frappe
from frappe import _
from frappe.utils import cint, getdate
from calendar import monthrange
from datetime import date, timedelta


DAY_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

MONTH_LIST = [
    ("January", 1), ("February", 2), ("March", 3), ("April", 4),
    ("May", 5), ("June", 6), ("July", 7), ("August", 8),
    ("September", 9), ("October", 10), ("November", 11), ("December", 12),
]


# ================================================================== #
# Entry point
# ================================================================== #

def execute(filters=None):
    filters = frappe._dict(filters or {})
    report_type = filters.get("report_type") or "Daily"
    summarized = bool(filters.get("summarized_view"))

    if summarized:
        if not (filters.month and filters.year):
            frappe.throw(_("Please select Month and Year"))
    else:
        if report_type in ("Daily", "Weekly") and not (filters.month and filters.year):
            frappe.throw(_("Please select Month and Year"))
        if report_type == "Monthly" and not filters.year:
            frappe.throw(_("Please select Year"))

    tracked_grades = _get_tracked_grades()
    if not tracked_grades:
        frappe.msgprint(
            _("No tracked grades configured in <b>Department Report Settings</b>."),
            alert=True, indicator="orange",
        )
        return _empty_columns(filters), []

    employees = _get_tracked_employees(tracked_grades, filters)
    if not employees:
        frappe.msgprint(
            _("No active employees found for the configured tracked grades."),
            alert=True, indicator="orange",
        )
        return _empty_columns(filters), []

    if summarized:
        return _execute_combined_summary(filters, employees)

    if report_type == "Daily":
        return _execute_daily(filters, employees)
    if report_type == "Weekly":
        return _execute_weekly(filters, employees)
    return _execute_monthly(filters, employees)


# ================================================================== #
# Settings + Employees
# ================================================================== #

def _get_tracked_grades():
    settings = frappe.get_single("Department Report Settings")
    return [g.grade for g in (settings.tracked_grades or []) if g.grade]


def _get_tracked_employees(grades, filters):
    emp_filters = {
        "status": "Active",
        "grade": ("in", grades),
    }
    if filters.company:
        emp_filters["company"] = filters.company
    if filters.department:
        emp_filters["department"] = filters.department

    return frappe.db.get_all(
        "Employee",
        filters=emp_filters,
        fields=[
            "name", "employee_name", "date_of_joining", "relieving_date",
            "grade", "department", "company", "holiday_list",
        ],
        order_by="employee_name",
    )


# ================================================================== #
# Daily branch (one column per date in the selected month)
# ================================================================== #

def _execute_daily(filters, employees):
    employee_ids = [e.name for e in employees]
    submission_map = _get_daily_submissions(filters, employee_ids)

    # Holiday lookup (only meaningful for Daily)
    company_defaults = {}
    holiday_list_names = set()
    for emp in employees:
        if emp.holiday_list:
            holiday_list_names.add(emp.holiday_list)
        elif emp.company:
            if emp.company not in company_defaults:
                company_defaults[emp.company] = frappe.get_cached_value(
                    "Company", emp.company, "default_holiday_list"
                )
            if company_defaults[emp.company]:
                holiday_list_names.add(company_defaults[emp.company])

    holiday_map = _get_holiday_map(holiday_list_names, filters)
    dates = _get_dates_in_month(filters)
    today = getdate()

    # Columns
    columns = _base_columns()
    for d in dates:
        columns.append({
            "label": f"{d.day} {DAY_ABBR[d.weekday()]}",
            "fieldname": d.strftime("%d_%m_%Y"),
            "fieldtype": "Data",
            "width": 65,
        })
    columns += _total_columns()

    # Rows
    rows = []
    for emp in employees:
        joining = getdate(emp.date_of_joining) if emp.date_of_joining else None
        relieving = getdate(emp.relieving_date) if emp.relieving_date else None
        submitted = submission_map.get(emp.name, set())
        effective_hl = emp.holiday_list or company_defaults.get(emp.company)
        holidays = holiday_map.get(effective_hl, []) if effective_hl else []

        row = _base_row(emp)
        total_s = total_m = 0

        for d in dates:
            key = d.strftime("%d_%m_%Y")

            if joining and d < joining:
                row[key] = ""; continue
            if relieving and d > relieving:
                row[key] = ""; continue
            if d > today:
                row[key] = ""; continue

            hstatus = _holiday_status(d, holidays)
            if hstatus:
                row[key] = hstatus
                continue

            if d in submitted:
                row[key] = "✅"; total_s += 1
            else:
                row[key] = "❌"; total_m += 1

        row["total_submitted"] = total_s
        row["total_missed"] = total_m
        rows.append(row)

    return columns, rows


def _get_daily_submissions(filters, employee_ids):
    if not employee_ids:
        return {}
    start, end = _month_range(filters)
    reports = frappe.db.get_all(
        "Department Report",
        filters={
            "report_type": "Daily",
            "report_date": ("between", [start, end]),
            "employee": ("in", employee_ids),
            "docstatus": ("!=", 2),
        },
        fields=["employee", "report_date"],
    )
    out = {}
    for r in reports:
        out.setdefault(r.employee, set()).add(getdate(r.report_date))
    return out


# ================================================================== #
# Weekly branch (one column per Monday in the selected month)
# ================================================================== #

def _execute_weekly(filters, employees):
    mondays = _mondays_in_month(filters)
    employee_ids = [e.name for e in employees]
    submission_map = _get_weekly_submissions(mondays, employee_ids)
    today = getdate()

    # Columns
    columns = _base_columns()
    for m in mondays:
        columns.append({
            "label": f"Wk {m.strftime('%b %d')}",
            "fieldname": f"wk_{m.strftime('%Y_%m_%d')}",
            "fieldtype": "Data",
            "width": 100,
        })
    columns += _total_columns()

    # Rows
    rows = []
    for emp in employees:
        joining = getdate(emp.date_of_joining) if emp.date_of_joining else None
        relieving = getdate(emp.relieving_date) if emp.relieving_date else None
        submitted = submission_map.get(emp.name, set())

        row = _base_row(emp)
        total_s = total_m = 0

        for monday in mondays:
            key = f"wk_{monday.strftime('%Y_%m_%d')}"
            week_end = monday + timedelta(days=6)

            # Pre-joining: entire week is before joining
            if joining and week_end < joining:
                row[key] = ""; continue
            # Post-relieving
            if relieving and monday > relieving:
                row[key] = ""; continue
            # Future week (not started yet)
            if monday > today:
                row[key] = ""; continue

            if monday in submitted:
                row[key] = "✅"; total_s += 1
            else:
                row[key] = "❌"; total_m += 1

        row["total_submitted"] = total_s
        row["total_missed"] = total_m
        rows.append(row)

    return columns, rows


def _mondays_in_month(filters):
    start, end = _month_range(filters)
    cur = start
    mondays = []
    while cur <= end:
        if cur.weekday() == 0:
            mondays.append(cur)
        cur += timedelta(days=1)
    return mondays


def _get_weekly_submissions(mondays, employee_ids):
    if not employee_ids or not mondays:
        return {}
    reports = frappe.db.get_all(
        "Department Report",
        filters={
            "report_type": "Weekly",
            "week_start_date": ("in", mondays),
            "employee": ("in", employee_ids),
            "docstatus": ("!=", 2),
        },
        fields=["employee", "week_start_date"],
    )
    out = {}
    for r in reports:
        out.setdefault(r.employee, set()).add(getdate(r.week_start_date))
    return out


# ================================================================== #
# Monthly branch (one column per month in the selected year)
# ================================================================== #

def _execute_monthly(filters, employees):
    year = cint(filters.year)
    employee_ids = [e.name for e in employees]
    submission_map = _get_monthly_submissions(year, employee_ids)
    today = getdate()

    # Columns
    columns = _base_columns()
    for m_name, _m_num in MONTH_LIST:
        columns.append({
            "label": m_name[:3],
            "fieldname": f"month_{m_name.lower()}",
            "fieldtype": "Data",
            "width": 70,
        })
    columns += _total_columns()

    # Rows
    rows = []
    for emp in employees:
        joining = getdate(emp.date_of_joining) if emp.date_of_joining else None
        relieving = getdate(emp.relieving_date) if emp.relieving_date else None
        submitted_months = submission_map.get(emp.name, set())

        row = _base_row(emp)
        total_s = total_m = 0

        for m_name, m_num in MONTH_LIST:
            key = f"month_{m_name.lower()}"
            month_start = date(year, m_num, 1)
            month_end = date(year, m_num, monthrange(year, m_num)[1])

            # Pre-joining: joining after the month ends
            if joining and month_end < joining:
                row[key] = ""; continue
            # Post-relieving
            if relieving and month_start > relieving:
                row[key] = ""; continue
            # Future month
            if month_start > today:
                row[key] = ""; continue

            # If month hasn't ended yet, don't penalize (incomplete period)
            if month_end > today:
                if m_name in submitted_months:
                    row[key] = "✅"; total_s += 1
                else:
                    row[key] = ""  # incomplete month, no ❌
                continue

            if m_name in submitted_months:
                row[key] = "✅"; total_s += 1
            else:
                row[key] = "❌"; total_m += 1

        row["total_submitted"] = total_s
        row["total_missed"] = total_m
        rows.append(row)

    return columns, rows


def _get_monthly_submissions(year, employee_ids):
    if not employee_ids:
        return {}
    reports = frappe.db.get_all(
        "Department Report",
        filters={
            "report_type": "Monthly",
            "report_year": year,
            "employee": ("in", employee_ids),
            "docstatus": ("!=", 2),
        },
        fields=["employee", "report_month"],
    )
    out = {}
    for r in reports:
        out.setdefault(r.employee, set()).add(r.report_month)
    return out


# ================================================================== #
# Combined summarised view — Daily + Weekly + Monthly on one row
# ================================================================== #

def _execute_combined_summary(filters, employees):
    employee_ids = [e.name for e in employees]
    today = getdate()
    year = cint(filters.year)

    # ---------- Daily ----------
    daily_submission_map = _get_daily_submissions(filters, employee_ids)

    company_defaults = {}
    holiday_list_names = set()
    for emp in employees:
        if emp.holiday_list:
            holiday_list_names.add(emp.holiday_list)
        elif emp.company:
            if emp.company not in company_defaults:
                company_defaults[emp.company] = frappe.get_cached_value(
                    "Company", emp.company, "default_holiday_list"
                )
            if company_defaults[emp.company]:
                holiday_list_names.add(company_defaults[emp.company])

    daily_holiday_map = _get_holiday_map(holiday_list_names, filters)
    dates = _get_dates_in_month(filters)

    # ---------- Weekly ----------
    mondays = _mondays_in_month(filters)
    weekly_submission_map = _get_weekly_submissions(mondays, employee_ids)

    # ---------- Monthly ----------
    monthly_submission_map = _get_monthly_submissions(year, employee_ids)

    # ---------- Columns ----------
    columns = _base_columns() + [
        # Daily
        {"label": _("Daily Working Days"), "fieldname": "d_working_days",
         "fieldtype": "Int", "width": 130},
        {"label": _("Daily Submitted"), "fieldname": "d_submitted",
         "fieldtype": "Int", "width": 120},
        {"label": _("Daily Missed"), "fieldname": "d_missed",
         "fieldtype": "Int", "width": 110},
        {"label": _("Daily WO"), "fieldname": "d_weekly_off",
         "fieldtype": "Int", "width": 90},
        {"label": _("Daily Holidays"), "fieldname": "d_holidays",
         "fieldtype": "Int", "width": 110},
        {"label": _("Daily Compliance %"), "fieldname": "d_compliance",
         "fieldtype": "Percent", "width": 140},

        # Weekly
        {"label": _("Weeks in Month"), "fieldname": "w_total",
         "fieldtype": "Int", "width": 110},
        {"label": _("Weekly Submitted"), "fieldname": "w_submitted",
         "fieldtype": "Int", "width": 130},
        {"label": _("Weekly Missed"), "fieldname": "w_missed",
         "fieldtype": "Int", "width": 120},
        {"label": _("Weekly Compliance %"), "fieldname": "w_compliance",
         "fieldtype": "Percent", "width": 150},

        # Monthly (for the year)
        {"label": _("Months in Year"), "fieldname": "m_total",
         "fieldtype": "Int", "width": 110},
        {"label": _("Monthly Submitted"), "fieldname": "m_submitted",
         "fieldtype": "Int", "width": 130},
        {"label": _("Monthly Missed"), "fieldname": "m_missed",
         "fieldtype": "Int", "width": 120},
        {"label": _("Monthly Compliance %"), "fieldname": "m_compliance",
         "fieldtype": "Percent", "width": 150},
    ]

    rows = []
    for emp in employees:
        joining = getdate(emp.date_of_joining) if emp.date_of_joining else None
        relieving = getdate(emp.relieving_date) if emp.relieving_date else None

        # ---------- Daily ----------
        d_submitted = daily_submission_map.get(emp.name, set())
        effective_hl = emp.holiday_list or company_defaults.get(emp.company)
        holidays_for_emp = daily_holiday_map.get(effective_hl, []) if effective_hl else []

        d_s = d_m = d_wo = d_h = 0
        for d in dates:
            if joining and d < joining: continue
            if relieving and d > relieving: continue
            if d > today: continue
            hstatus = _holiday_status(d, holidays_for_emp)
            if hstatus == "WO":
                d_wo += 1; continue
            if hstatus == "H":
                d_h += 1; continue
            if d in d_submitted:
                d_s += 1
            else:
                d_m += 1
        d_working = d_s + d_m
        d_compliance = (d_s / d_working * 100) if d_working else 0

        # ---------- Weekly ----------
        w_submitted = weekly_submission_map.get(emp.name, set())
        w_s = w_m = 0
        for monday in mondays:
            week_end = monday + timedelta(days=6)
            if joining and week_end < joining: continue
            if relieving and monday > relieving: continue
            if monday > today: continue
            if monday in w_submitted:
                w_s += 1
            else:
                w_m += 1
        w_total = w_s + w_m
        w_compliance = (w_s / w_total * 100) if w_total else 0

        # ---------- Monthly ----------
        m_submitted_set = monthly_submission_map.get(emp.name, set())
        m_s = m_m = 0
        for m_name, m_num in MONTH_LIST:
            month_start = date(year, m_num, 1)
            month_end = date(year, m_num, monthrange(year, m_num)[1])
            if joining and month_end < joining: continue
            if relieving and month_start > relieving: continue
            if month_start > today: continue
            if month_end > today:
                if m_name in m_submitted_set:
                    m_s += 1
                continue
            if m_name in m_submitted_set:
                m_s += 1
            else:
                m_m += 1
        m_total = m_s + m_m
        m_compliance = (m_s / m_total * 100) if m_total else 0

        row = _base_row(emp)
        row.update({
            "d_working_days": d_working,
            "d_submitted": d_s,
            "d_missed": d_m,
            "d_weekly_off": d_wo,
            "d_holidays": d_h,
            "d_compliance": d_compliance,
            "w_total": w_total,
            "w_submitted": w_s,
            "w_missed": w_m,
            "w_compliance": w_compliance,
            "m_total": m_total,
            "m_submitted": m_s,
            "m_missed": m_m,
            "m_compliance": m_compliance,
        })
        rows.append(row)

    return columns, rows


# ================================================================== #
# Holiday lookup (Daily only)
# ================================================================== #

def _get_holiday_map(holiday_list_names, filters):
    start, end = _month_range(filters)
    holiday_map = {}
    for hl in holiday_list_names:
        if not hl or hl in holiday_map:
            continue
        holidays = frappe.db.get_all(
            "Holiday",
            filters={"parent": hl, "holiday_date": ("between", [start, end])},
            fields=["holiday_date", "weekly_off"],
        )
        holiday_map[hl] = [(getdate(h.holiday_date), h.weekly_off) for h in holidays]
    return holiday_map


def _holiday_status(d, holidays):
    for holiday_date, weekly_off in holidays:
        if d == holiday_date:
            return "WO" if weekly_off else "H"
    return None


# ================================================================== #
# Shared helpers
# ================================================================== #

def _base_columns():
    return [
        {"label": _("Employee"), "fieldname": "employee", "fieldtype": "Link",
         "options": "Employee", "width": 130},
        {"label": _("Employee Name"), "fieldname": "employee_name",
         "fieldtype": "Data", "width": 180},
        {"label": _("Grade"), "fieldname": "grade", "fieldtype": "Link",
         "options": "Employee Grade", "width": 130},
        {"label": _("Department"), "fieldname": "department", "fieldtype": "Link",
         "options": "Department", "width": 150},
    ]


def _total_columns():
    return [
        {"label": _("Submitted"), "fieldname": "total_submitted",
         "fieldtype": "Int", "width": 100},
        {"label": _("Missed"), "fieldname": "total_missed",
         "fieldtype": "Int", "width": 90},
    ]


def _base_row(emp):
    return {
        "employee": emp.name,
        "employee_name": emp.employee_name,
        "grade": emp.grade,
        "department": emp.department,
    }


def _empty_columns(filters):
    return _base_columns() + _total_columns()


def _month_range(filters):
    month = cint(filters.month)
    year = cint(filters.year)
    last_day = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def _get_dates_in_month(filters):
    start, end = _month_range(filters)
    return [date(start.year, start.month, day) for day in range(1, end.day + 1)]
