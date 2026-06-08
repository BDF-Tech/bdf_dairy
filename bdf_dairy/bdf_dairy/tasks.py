import frappe
from frappe.utils import nowdate, get_url

from bdf_dairy.bdf_dairy.doctype.department_report.department_report import (
    _get_bot_user,
    _post_to_raven_channel,
    _send_raven_dm,
)


def send_daily_report_reminder():
    """
    Runs daily at ~17:30. Finds all active employees linked to a User who
    have the 'Department Head' role but have NOT submitted a Daily Report
    for today. Sends a reminder via Raven DM + email.
    """
    today = nowdate()

    # Employees who already submitted today
    submitted_employees = frappe.db.sql("""
        SELECT employee FROM `tabDepartment Report`
        WHERE report_type = 'Daily'
          AND report_date = %s
          AND docstatus != 2
    """, today, as_list=True)
    submitted_set = {r[0] for r in submitted_employees}

    # All active employees who are linked to a user with 'Department Head' role
    dept_head_users = frappe.db.sql("""
        SELECT DISTINCT u.name
        FROM `tabUser` u
        JOIN `tabHas Role` hr ON hr.parent = u.name
        WHERE hr.role = 'Department Head'
          AND u.enabled = 1
    """, as_list=True)
    dept_head_user_ids = {r[0] for r in dept_head_users}

    pending_employees = frappe.db.get_all("Employee", filters={
        "status": "Active",
        "user_id": ["in", list(dept_head_user_ids)],
        "name": ["not in", list(submitted_set)] if submitted_set else ["!=", ""],
    }, fields=["name", "employee_name", "department", "user_id"])

    if not pending_employees:
        return

    bot_user = _get_bot_user()
    site_url = get_url()
    new_report_link = f"{site_url}/app/department-report/new-department-report-1"

    for emp in pending_employees:
        if not emp.user_id:
            continue

        reminder_text = (
            f"⏰ **Daily Report Reminder**\n\n"
            f"Hi {emp.employee_name}, you haven't submitted your Daily Report for today ({today}).\n\n"
            f"Please submit it before end of day.\n\n"
            f"[Submit Report Now]({new_report_link})"
        )

        # Raven DM
        _send_raven_dm(emp.user_id, reminder_text, bot_user)

        # Email
        frappe.sendmail(
            recipients=[emp.user_id],
            subject=f"Reminder: Daily Report Pending — {today}",
            message=f"""
            <p>Hi <b>{emp.employee_name}</b>,</p>
            <p>This is a reminder that your <b>Daily Report</b> for <b>{today}</b> has not been submitted yet.</p>
            <p>Please submit it before end of day.</p>
            <a href="{new_report_link}" style="background:#1a73e8;color:white;padding:8px 20px;border-radius:4px;text-decoration:none">
                Submit Report
            </a>
            """,
        )

    frappe.logger().info(
        f"[Department Report] Reminder sent to {len(pending_employees)} employee(s) for {today}"
    )
