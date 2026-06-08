import frappe
from frappe.model.document import Document
from frappe.utils import now, getdate, add_days


class DepartmentReport(Document):

    def before_save(self):
        if self.report_type == "Weekly" and self.week_start_date:
            self.week_end_date = str(add_days(getdate(self.week_start_date), 6))
        if not self.submitted_by_user:
            self.submitted_by_user = frappe.session.user

    def validate(self):
        self._check_duplicate()
        self._validate_mandatory_tables()

    def on_submit(self):
        grade = frappe.db.get_value("Employee", self.employee, "grade")
        if grade == "Department Head":
            self._send_email_to_md()

    # ------------------------------------------------------------------ #
    # Validations
    # ------------------------------------------------------------------ #

    def _validate_mandatory_tables(self):
        if not self.completed_items:
            frappe.throw("Completed Work section cannot be empty. Please add at least one item.")
        if not self.ongoing_items:
            frappe.throw("Ongoing Work section cannot be empty. Please add at least one item.")
        if not self.pending_items:
            frappe.throw("Pending / Blocked Work section cannot be empty. Please add at least one item.")
        if self.report_type == "Daily" and not self.daily_timeline:
            frappe.throw("Daily Timeline cannot be empty. Please add at least one timeline entry.")

    def _check_duplicate(self):
        if self.report_type == "Daily" and self.report_date and self.department:
            exists = frappe.db.exists("Department Report", {
                "report_type": "Daily", "department": self.department,
                "report_date": self.report_date, "name": ("!=", self.name), "docstatus": ("!=", 2),
            })
            if exists:
                frappe.throw(f"A Daily Report for <b>{self.department}</b> on <b>{self.report_date}</b> already exists: {exists}")

        if self.report_type == "Weekly" and self.week_start_date and self.department:
            exists = frappe.db.exists("Department Report", {
                "report_type": "Weekly", "department": self.department,
                "week_start_date": self.week_start_date, "name": ("!=", self.name), "docstatus": ("!=", 2),
            })
            if exists:
                frappe.throw(f"A Weekly Report for <b>{self.department}</b> starting <b>{self.week_start_date}</b> already exists: {exists}")

        if self.report_type == "Monthly" and self.report_month and self.report_year and self.department:
            exists = frappe.db.exists("Department Report", {
                "report_type": "Monthly", "department": self.department,
                "report_month": self.report_month, "report_year": self.report_year,
                "name": ("!=", self.name), "docstatus": ("!=", 2),
            })
            if exists:
                frappe.throw(f"A Monthly Report for <b>{self.department}</b> - <b>{self.report_month} {self.report_year}</b> already exists: {exists}")

    # ------------------------------------------------------------------ #
    # Email to MD
    # ------------------------------------------------------------------ #

    def _send_email_to_md(self):
        settings = frappe.get_single("Department Report Settings")
        md_email = (settings.md_email or "").strip()

        if not md_email:
            frappe.log_error(
                f"Department Report {self.name}: MD Email is not set in Department Report Settings",
                "Department Report — Missing MD Email",
            )
            return

        context = self._template_context()
        subject = self._render(settings.email_subject or "", context)
        body = self._render(settings.email_body or "", context)

        frappe.sendmail(recipients=[md_email], subject=subject, message=body)

        frappe.db.set_value(
            "Department Report",
            self.name,
            {"submitted_to_md": 1, "md_notified_at": now()},
        )

    def _template_context(self):
        site_url = frappe.utils.get_url()
        return {
            "report_type": self.report_type or "",
            "department": self.department or "",
            "department_head": self.department_head or "",
            "period": self._period_str(),
            "report_link": f"{site_url}/app/department-report/{self.name}",
            "completed_count": len(self.completed_items or []),
            "ongoing_count": len(self.ongoing_items or []),
            "pending_count": len(self.pending_items or []),
            "blockers_count": len(self.blockers or []),
            "support_needed": self.support_needed_from_md or "-",
            "overall_remarks": self.overall_remarks or "-",
        }

    def _period_str(self):
        if self.report_type == "Daily":
            return str(self.report_date or "")
        if self.report_type == "Weekly":
            return f"{self.week_start_date} to {self.week_end_date}"
        return f"{self.report_month} {self.report_year}"

    def _render(self, template, context):
        result = template
        for key, value in context.items():
            result = result.replace("{" + key + "}", str(value))
        return result
