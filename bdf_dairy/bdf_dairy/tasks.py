import frappe
from frappe.utils import nowdate, get_url


def send_daily_report_reminder():
    """
    Runs daily at 17:30 (cron in hooks.py).
    Reminds all active employees whose grade is 'Department Head' and who
    haven't submitted a Daily Report for today.
    Reminder is sent via email only.
    """
    today = nowdate()

    submitted = frappe.db.get_all(
        "Department Report",
        filters={
            "report_type": "Daily",
            "report_date": today,
            "docstatus": ("!=", 2),
        },
        pluck="employee",
    )

    filters = {
        "status": "Active",
        "grade": "Department Head",
        "user_id": ("!=", ""),
    }
    if submitted:
        filters["name"] = ("not in", submitted)

    pending = frappe.db.get_all(
        "Employee",
        filters=filters,
        fields=["name", "employee_name", "user_id"],
    )

    if not pending:
        return

    site_url = get_url()
    new_link = f"{site_url}/app/department-report/new?doctype=Department%20Report"

    for emp in pending:
        if not emp.user_id:
            continue

        frappe.sendmail(
            recipients=[emp.user_id],
            subject=f"Reminder: Daily Report Pending — {today}",
            message=f"""
            <p>Hi <b>{emp.employee_name}</b>,</p>
            <p>This is a reminder that your <b>Daily Report</b> for <b>{today}</b> has not been submitted yet.</p>
            <p>Please submit it before end of day.</p>
            <p>
              <a href="{new_link}" style="background:#1a73e8;color:white;padding:8px 20px;border-radius:4px;text-decoration:none">
                Submit Report
              </a>
            </p>
            """,
        )

    frappe.logger().info(
        f"[Department Report] Reminder sent to {len(pending)} employee(s) for {today}"
    )
