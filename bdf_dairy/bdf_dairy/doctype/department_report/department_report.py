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
        grade = frappe.db.get_value("Employee", self.employee, "grade") if self.employee else None

        if grade != "Department Head":
            frappe.msgprint(
                f"Report submitted.<br>Email <b>not sent</b> — Employee grade is <b>{grade or 'not set'}</b>, "
                f"not <b>Department Head</b>.",
                title="Email Not Sent",
                indicator="orange",
            )
            return

        settings = frappe.get_single("Department Report Settings")
        recipients = [
            (r.email_address or "").strip()
            for r in (settings.recipients or [])
            if r.enabled and (r.email_address or "").strip()
        ]

        if not recipients:
            frappe.msgprint(
                "Report submitted.<br>Email <b>not sent</b> — no enabled recipients configured in "
                "<b>Department Report Settings</b>.",
                title="Email Not Sent",
                indicator="red",
            )
            return

        if not settings.active_template:
            frappe.msgprint(
                "Report submitted.<br>Email <b>not sent</b> — no Active Email Template set in "
                "<b>Department Report Settings</b>.",
                title="Email Not Sent",
                indicator="red",
            )
            return

        template = frappe.db.get_value(
            "Department Report Template",
            settings.active_template,
            ["email_subject", "email_html", "email_css", "email_js", "enabled"],
            as_dict=True,
        )

        if not template:
            frappe.msgprint(
                f"Report submitted.<br>Email <b>not sent</b> — template "
                f"<b>{settings.active_template}</b> not found.",
                title="Email Not Sent",
                indicator="red",
            )
            return

        if not template.enabled:
            frappe.msgprint(
                f"Report submitted.<br>Email <b>not sent</b> — template "
                f"<b>{settings.active_template}</b> is disabled.",
                title="Email Not Sent",
                indicator="red",
            )
            return

        try:
            self._send_email_to_md(template, recipients)
            frappe.msgprint(
                f"Report submitted and email <b>queued for delivery</b> to:<br>"
                f"<b>{', '.join(recipients)}</b><br><br>"
                f"Template: <b>{settings.active_template}</b>",
                title="Email Sent to MD",
                indicator="green",
            )
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Department Report — Email send failed")
            frappe.msgprint(
                f"Report submitted but email <b>failed</b>: {frappe.utils.escape_html(str(e))}<br>"
                f"See Error Log for details.",
                title="Email Failed",
                indicator="red",
            )

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
    # Email to MD — Jinja rendering
    # ------------------------------------------------------------------ #

    def _send_email_to_md(self, template, recipients):
        context = {
            "doc": self,
            "period": self._period_str(),
            "report_link": f"{frappe.utils.get_url()}/app/department-report/{self.name}",
        }

        subject = frappe.render_template(template.email_subject or "", context)
        html = frappe.render_template(template.email_html or "", context)
        css = frappe.render_template(template.email_css or "", context) if template.email_css else ""
        js = frappe.render_template(template.email_js or "", context) if template.email_js else ""

        parts = []
        if css.strip():
            parts.append(f"<style>{css}</style>")
        parts.append(html)
        if js.strip():
            parts.append(f"<script>{js}</script>")
        body = "\n".join(parts)

        frappe.sendmail(recipients=recipients, subject=subject, message=body)

        frappe.db.set_value(
            "Department Report",
            self.name,
            {"submitted_to_md": 1, "md_notified_at": now()},
        )

    def _period_str(self):
        if self.report_type == "Daily":
            return str(self.report_date or "")
        if self.report_type == "Weekly":
            return f"{self.week_start_date} to {self.week_end_date}"
        return f"{self.report_month} {self.report_year}"
