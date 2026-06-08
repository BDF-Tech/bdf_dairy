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
            self._send_md_notification()
            frappe.db.set_value("Department Report", self.name, {
                "submitted_to_md": 1,
                "md_notified_at": now(),
            })

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
    # Notify MD — email + Raven
    # ------------------------------------------------------------------ #

    def _send_md_notification(self):
        settings = frappe.get_single("Department Report Settings")
        md_email = (settings.md_email or "").strip()

        if not md_email:
            frappe.log_error(
                f"Department Report {self.name}: MD Email not set in Department Report Settings",
                "Department Report — Missing MD Email",
            )
        else:
            context = self._get_template_context()
            subject = self._render_template(settings.email_subject or "", context)
            body = self._render_template(settings.email_body or "", context)
            frappe.sendmail(recipients=[md_email], subject=subject, message=body)

        # Raven still posts to the channel; DM the MD user if their email is also a User
        md_user = frappe.db.exists("User", md_email) if md_email else None
        self._send_raven_notification([md_user] if md_user else [])

    def _get_template_context(self):
        site_url = frappe.utils.get_url()
        return {
            "report_type": self.report_type or "",
            "department": self.department or "",
            "department_head": self.department_head or "",
            "period": self._get_period_str(),
            "report_link": f"{site_url}/app/department-report/{self.name}",
            "completed_count": len(self.completed_items or []),
            "ongoing_count": len(self.ongoing_items or []),
            "pending_count": len(self.pending_items or []),
            "blockers_count": len(self.blockers or []),
            "support_needed": self.support_needed_from_md or "-",
            "overall_remarks": self.overall_remarks or "-",
        }

    def _render_template(self, template, context):
        result = template
        for key, value in context.items():
            result = result.replace("{" + key + "}", str(value))
        return result

    # ------------------------------------------------------------------ #
    # Raven
    # ------------------------------------------------------------------ #

    def _send_raven_notification(self, md_users):
        raven_text = self._build_raven_text()
        bot_user = _get_bot_user()

        # 1. Post to the reports channel if it exists
        _post_to_raven_channel("Raven-bdf-operation", raven_text, bot_user)

        # 2. Send DM to each MD user
        for user in md_users:
            _send_raven_dm(user, raven_text, bot_user)

    def _build_raven_text(self):
        site_url = frappe.utils.get_url()
        link = f"{site_url}/app/department-report/{self.name}"

        period = self._get_period_str()
        lines = [
            f"📋 **{self.report_type} Report Submitted**",
            f"**Department:** {self.department}   |   **By:** {self.department_head or self.employee}   |   **Period:** {period}",
            "",
            f"✅ Completed: {len(self.completed_items)} item(s)",
            f"🔄 Ongoing: {len(self.ongoing_items)} item(s)",
            f"⏳ Pending: {len(self.pending_items)} item(s)",
        ]

        if self.blockers:
            lines.append(f"🚧 Blockers: {len(self.blockers)} item(s)")

        if self.support_needed_from_md:
            lines.append(f"\n**⚠️ Support needed from MD:**\n{self.support_needed_from_md}")

        lines.append(f"\n[View Full Report]({link})")
        return "\n".join(lines)

    def _get_period_str(self):
        if self.report_type == "Daily":
            return str(self.report_date or "")
        if self.report_type == "Weekly":
            return f"{self.week_start_date} to {self.week_end_date}"
        return f"{self.report_month} {self.report_year}"

# ------------------------------------------------------------------ #
# Raven helpers (module level — also used by tasks.py)
# ------------------------------------------------------------------ #

def _get_bot_user():
    raven_user = frappe.db.get_value("Raven Bot", {"bot_name": "bdf-bot"}, "raven_user")
    if raven_user:
        user = frappe.db.get_value("Raven User", raven_user, "user")
        if user:
            return user
    return "Administrator"


def _post_to_raven_channel(channel_id, text, sender=None):
    if not frappe.db.exists("Raven Channel", channel_id):
        return
    try:
        msg = frappe.new_doc("Raven Message")
        msg.channel_id = channel_id
        msg.text = text
        msg.message_type = "Text"
        if sender:
            msg.owner = sender
        msg.flags.ignore_permissions = True
        msg.insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Raven channel post failed")


def _send_raven_dm(user_id, text, sender=None):
    if not frappe.db.exists("User", user_id):
        return
    try:
        from raven.api.raven_channel import create_direct_message_channel
        frappe.set_user(sender or "Administrator")
        channel = create_direct_message_channel(user_id)
        channel_id = channel.get("name") if isinstance(channel, dict) else channel.name
        _post_to_raven_channel(channel_id, text, sender)
        frappe.set_user("Administrator")
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Raven DM failed")
