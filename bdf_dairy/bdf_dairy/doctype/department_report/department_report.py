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
        recipients = self._get_md_recipients()
        if recipients:
            frappe.sendmail(
                recipients=list(recipients),
                subject=self._build_subject(),
                message=self._build_email_body(),
            )
        self._send_raven_notification(recipients)

    def _get_md_recipients(self):
        recipients = set()
        md_employees = frappe.db.get_all("Employee", filters={
            "designation": ["in", ["Managing Director", "MD", "Director", "CEO", "Chief Executive Officer"]],
            "status": "Active",
        }, fields=["user_id"])
        for emp in md_employees:
            if emp.user_id:
                recipients.add(emp.user_id)

        if not recipients:
            sys_managers = frappe.db.sql("""
                SELECT DISTINCT u.name FROM `tabUser` u
                JOIN `tabHas Role` hr ON hr.parent = u.name
                WHERE hr.role = 'System Manager' AND u.enabled = 1 AND u.name != 'Administrator'
                LIMIT 5
            """, as_dict=True)
            for u in sys_managers:
                recipients.add(u.name)
        return recipients

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
    # Email body builders
    # ------------------------------------------------------------------ #

    def _build_subject(self):
        if self.report_type == "Daily":
            return f"Daily Report | {self.department} | {self.report_date}"
        elif self.report_type == "Weekly":
            return f"Weekly Report | {self.department} | {self.week_start_date} to {self.week_end_date}"
        return f"Monthly Report | {self.department} | {self.report_month} {self.report_year}"

    def _build_email_body(self):
        site_url = frappe.utils.get_url()
        doc_link = f"{site_url}/app/department-report/{self.name}"
        period_html = self._get_period_str()

        completed_html = self._work_table_html(self.completed_items, "Completed Work", "#27ae60")
        ongoing_html = self._work_table_html(self.ongoing_items, "Ongoing Work", "#f39c12")
        pending_html = self._work_table_html(self.pending_items, "Pending / Blocked Work", "#e74c3c")
        blockers_html = self._blockers_html()

        extra = ""
        if self.report_type == "Daily":
            extra += self._timeline_html()
            if self.tomorrows_plan:
                extra += f"<h3 style='color:#27ae60'>Tomorrow's Plan</h3><div style='padding:10px;background:#f0fff4;border-left:4px solid #27ae60'>{self.tomorrows_plan}</div>"
        elif self.report_type == "Weekly":
            if self.issues_faced:
                extra += f"<h3 style='color:#c0392b'>Issues Faced</h3><div style='padding:10px;background:#fff5f5;border-left:4px solid #c0392b'>{self.issues_faced}</div>"
            if self.next_week_plan:
                extra += f"<h3 style='color:#27ae60'>Plan for Next Week</h3><div style='padding:10px;background:#f0fff4;border-left:4px solid #27ae60'>{self.next_week_plan}</div>"
        elif self.report_type == "Monthly":
            if self.key_achievements:
                extra += f"<h3 style='color:#2980b9'>Key Achievements</h3><div style='padding:10px;background:#ebf5fb;border-left:4px solid #2980b9'>{self.key_achievements}</div>"
            extra += self._kpi_table_html()
            if self.next_month_plan:
                extra += f"<h3 style='color:#27ae60'>Plan for Next Month</h3><div style='padding:10px;background:#f0fff4;border-left:4px solid #27ae60'>{self.next_month_plan}</div>"

        support_html = ""
        if self.support_needed_from_md:
            support_html = f"""
            <div style="background:#fff3cd;border-left:4px solid #ffc107;padding:12px;margin:15px 0;border-radius:4px">
                <strong>⚠️ Support / Decision Needed from MD:</strong><br>{self.support_needed_from_md}
            </div>"""

        return f"""
        <div style="font-family:Arial,sans-serif;max-width:800px;margin:auto">
            <div style="background:#1a73e8;color:white;padding:20px;border-radius:8px 8px 0 0">
                <h2 style="margin:0">{self.report_type} Department Report</h2>
                <p style="margin:5px 0 0 0;opacity:0.9">{self.department} &nbsp;|&nbsp; {self.department_head or self.employee} &nbsp;|&nbsp; {period_html}</p>
            </div>
            <div style="padding:20px;border:1px solid #dee2e6;border-top:none">
                {support_html}
                {completed_html}{ongoing_html}{pending_html}
                {blockers_html}{extra}
                {'<p><strong>Remarks:</strong> ' + self.overall_remarks + '</p>' if self.overall_remarks else ''}
                <div style="margin-top:30px;text-align:center">
                    <a href="{doc_link}" style="background:#1a73e8;color:white;padding:10px 25px;border-radius:4px;text-decoration:none;font-weight:bold">
                        View Full Report in ERPNext
                    </a>
                </div>
            </div>
        </div>"""

    def _work_table_html(self, items, heading, color):
        priority_colors = {"High": "#e74c3c", "Medium": "#f39c12", "Low": "#27ae60"}
        if not items:
            return f"<h3 style='color:{color}'>{heading}</h3><p style='color:#888'><em>Nothing to report</em></p>"
        rows = "".join(
            f"<tr><td style='padding:8px;border-bottom:1px solid #eee'>{i.title}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;"
            f"color:{priority_colors.get(i.priority, '#888')};font-weight:bold'>{i.priority or '-'}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;color:#555'>{i.description or ''}</td></tr>"
            for i in items
        )
        return f"""<h3 style="color:{color};border-bottom:2px solid {color};padding-bottom:5px">{heading}</h3>
        <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:20px">
            <thead><tr style="background:{color};color:white">
                <th style="padding:8px;text-align:left">Task</th>
                <th style="padding:8px;text-align:left">Priority</th>
                <th style="padding:8px;text-align:left">Notes</th>
            </tr></thead><tbody>{rows}</tbody></table>"""

    def _blockers_html(self):
        if not self.blockers:
            return ""
        rows = "".join(
            f"<tr><td style='padding:8px;border-bottom:1px solid #eee'>{b.blocker_title}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;color:#e74c3c'>{b.blocked_by or '-'}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;color:#555'>{b.details or ''}</td></tr>"
            for b in self.blockers
        )
        return f"""<h3 style="color:#8e44ad;border-bottom:2px solid #8e44ad;padding-bottom:5px">🚧 Blockers</h3>
        <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:20px">
            <thead><tr style="background:#8e44ad;color:white">
                <th style="padding:8px;text-align:left">Blocker</th>
                <th style="padding:8px;text-align:left">Blocked By</th>
                <th style="padding:8px;text-align:left">Details</th>
            </tr></thead><tbody>{rows}</tbody></table>"""

    def _timeline_html(self):
        if not self.daily_timeline:
            return ""
        rows = "".join(
            f"<tr><td style='padding:8px;border-bottom:1px solid #eee;font-weight:bold'>{e.time or ''}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee'>{e.activity}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;color:#555'>{e.description or ''}</td></tr>"
            for e in self.daily_timeline
        )
        return f"""<h3 style="color:#8e44ad;border-bottom:2px solid #8e44ad;padding-bottom:5px">Daily Timeline</h3>
        <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:20px">
            <thead><tr style="background:#8e44ad;color:white">
                <th style="padding:8px;text-align:left">Time</th>
                <th style="padding:8px;text-align:left">Activity</th>
                <th style="padding:8px;text-align:left">Details</th>
            </tr></thead><tbody>{rows}</tbody></table>"""

    def _kpi_table_html(self):
        if not self.kpi_metrics:
            return ""
        rows = "".join(
            f"<tr><td style='padding:8px;border-bottom:1px solid #eee'>{k.metric_name}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;text-align:right'>{k.target or '-'}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;text-align:right'>{k.actual if k.actual is not None else '-'}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee'>{k.unit or ''}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;color:#555'>{k.remarks or ''}</td></tr>"
            for k in self.kpi_metrics
        )
        return f"""<h3 style="color:#2980b9;border-bottom:2px solid #2980b9;padding-bottom:5px">KPI / Metrics</h3>
        <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:20px">
            <thead><tr style="background:#2980b9;color:white">
                <th style="padding:8px;text-align:left">Metric</th>
                <th style="padding:8px;text-align:right">Target</th>
                <th style="padding:8px;text-align:right">Actual</th>
                <th style="padding:8px;text-align:left">Unit</th>
                <th style="padding:8px;text-align:left">Remarks</th>
            </tr></thead><tbody>{rows}</tbody></table>"""


# ------------------------------------------------------------------ #
# Raven helpers (module level — also used by tasks.py)
# ------------------------------------------------------------------ #

def _get_bot_user():
    bot = frappe.db.get_value("Raven Bot", {"bot_name": "bdf-bot"}, "name")
    if bot:
        return frappe.db.get_value("Raven Bot", bot, "user")
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
