import frappe
from frappe.model.document import Document


class DepartmentReportSettings(Document):
    def validate(self):
        enabled = [
            (r.email_address or "").strip()
            for r in (self.recipients or [])
            if r.enabled and (r.email_address or "").strip()
        ]
        if not enabled:
            frappe.throw(
                "Please add at least one enabled recipient with a valid email address."
            )

        for r in self.recipients or []:
            email = (r.email_address or "").strip()
            if email and "@" not in email:
                frappe.throw(f"Invalid email address: <b>{email}</b>")

        if self.active_template:
            tmpl_enabled = frappe.db.get_value(
                "Department Report Template", self.active_template, "enabled"
            )
            if not tmpl_enabled:
                frappe.throw(
                    f"Selected template <b>{self.active_template}</b> is disabled. "
                    f"Enable it or pick another template."
                )
