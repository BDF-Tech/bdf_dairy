# Copyright (c) 2025, BDF and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import add_days, flt, formatdate, get_first_day, get_last_day, getdate
from frappe.utils.synchronization import filelock
from frappe.utils.file_lock import LockTimeoutError

from bdf_dairy.bdf_dairy.doctype.farmer_incentive_settings.farmer_incentive_settings import (
    get_incentive_rate,
)


MILK_TYPE_TO_SETTING = {
    "Cow": "cow_pro",
    "Buffalo": "buf_pro",
    "Mix": "mix_pro",
}


class FarmerBilling(Document):
    def autoname(self):
        pattern = f"{self.from_date}--{self.to_date}--{self.dcs}%"
        counter = frappe.db.count("Farmer Billing", filters={"name": ["like", pattern]})
        self.name = f"{self.from_date}--{self.to_date}--{self.dcs}--{counter + 1}"

    def before_submit(self):
        # Month-end billing: fix the team lead payout before anything is created
        if self.set_month_payout():
            self.incentive_paid_in = self.name
        # Layer 1 — catch all predictable issues BEFORE any PI is created
        self.validate_pi_creation_data()
        self.creation_status = "Pending"

    def on_submit(self):
        self.mark_incentive_paid()
        # Per-PI atomic commit. Idempotent. Continues on per-farmer error.
        self.create_purchase_invoice()

    def before_save(self):
        self.set_adjustments()
        self.get_running_total()

    def set_adjustments(self):
        """
        Net Amount is what the farmer is actually paid. Do Billing fills it with the
        calculated amount; whoever edits it here must say why, and the difference is
        carried to the farmer's Purchase Invoice as one adjustment row.
        """
        for row in self.farmer_billing_summary:
            # An untouched row (no reason given) simply follows the calculated amount
            if not flt(row.net_amount) and not (row.adjustment_reason or "").strip():
                row.net_amount = row.amount

            row.adjustment_amount = flt(flt(row.net_amount) - flt(row.amount), 2)

            if row.adjustment_amount and not (row.adjustment_reason or "").strip():
                frappe.throw(
                    f"Farmer <b>{row.farmer}</b>: Net Amount was changed from "
                    f"{flt(row.amount, 2)} to {flt(row.net_amount, 2)}. Please give an Adjustment Reason.",
                    title="Reason Needed",
                )

    def get_running_total(self):
        total_qty, total_amount, total_incentive, total_adjustment, total_net = 0, 0, 0, 0, 0
        for row in self.farmer_billing_summary:
            total_qty += row.qty
            total_amount += row.amount
            total_incentive += flt(row.incentive_amount)
            total_adjustment += flt(row.adjustment_amount)
            total_net += flt(row.net_amount)

        self.total_qty = total_qty
        self.average_rate = (total_amount / total_qty) if total_qty else 0
        self.total_amount = total_amount
        self.total_incentive = total_incentive
        self.total_adjustment = total_adjustment
        self.total_net_amount = total_net

    @frappe.whitelist()
    def get_milk_entry_detail_data(self):
        self.farmer_billing_details.clear()
        # Cleared here too: the form clears it client-side, but a second server-side call
        # would otherwise append a duplicate set of farmers and double every total.
        self.farmer_billing_summary.clear()
        if not self.from_date:
            frappe.throw("From Date Is Missing.")

        if not self.no_of_date:
            frappe.throw("Number Of Days Is Missing.")

        if not self.dcs:
            frappe.throw("DCS Is Missing.")

        milk_entries = frappe.get_all(
            "Milk Entry",
            filters={
                "date": ["between", [self.from_date, self.to_date]],
                "dcs_id": self.dcs,
                "docstatus": 1,
                "status": ["!=", "Billed"],
            },
            fields=[
                "name", "date", "shift", "member", "member_name", "milk_type",
                "fat", "snf", "volume", "unit_price_with_incentive",
            ],
            order_by="member_name ASC, date ASC, shift DESC",
        )

        if not milk_entries:
            frappe.throw("No Milk Entry Found.")

        entry_names = [entry["name"] for entry in milk_entries]
        receipt_map = frappe._dict({
            d.milk_entry: d.name for d in frappe.get_all(
                "Purchase Receipt",
                filters={"milk_entry": ["in", entry_names]},
                fields=["milk_entry", "name"],
            )
        })

        farmer_summary = {}

        for entry in milk_entries:
            volume = entry["volume"] or 0
            rate = entry["unit_price_with_incentive"] or 0
            amount = volume * rate
            member = entry["member"]
            member_name = entry["member_name"]

            self.append("farmer_billing_details", {
                "milk_entry_date": entry["date"],
                "milk_entry_shift": entry["shift"],
                "milk_entry": entry["name"],
                "milk_type": entry["milk_type"],
                "farmer": member,
                "farmer_name": member_name,
                "purchase_receipt": receipt_map.get(entry["name"]),
                "fat_": entry["fat"],
                "snf_": entry["snf"],
                "qty": volume,
                "rate": rate,
                "amount": amount,
            })

            if member not in farmer_summary:
                farmer_summary[member] = {
                    "member_name": member_name,
                    "total_qty": 0,
                    "total_amount": 0,
                    "entry_count": 0,
                }

            farmer_summary[member]["total_qty"] += volume
            farmer_summary[member]["total_amount"] += amount
            farmer_summary[member]["entry_count"] += 1

        for member, data in farmer_summary.items():
            self.append("farmer_billing_summary", {
                "farmer": member,
                "farmer_name": data["member_name"],
                "qty": data["total_qty"],
                "rate": data["total_amount"] / data["total_qty"] if data["total_qty"] else 0,
                "amount": data["total_amount"],
                "net_amount": data["total_amount"],
            })
        self.set_team_lead_incentive()
        self.get_running_total()

    # ================================================================== #
    # Re-pricing — when a Milk Rate was corrected after the entries were made
    # ================================================================== #

    @frappe.whitelist()
    def preview_milk_rate_changes(self):
        """
        What a re-price would change, worked out in memory. Nothing is written, so this
        can be shown for confirmation before the rates are actually applied.
        """
        if self.docstatus != 0:
            frappe.throw("Rates can only be recalculated while the Farmer Billing is a draft.")
        if not self.farmer_billing_details:
            frappe.throw("Nothing to check. Use 'Do Billing' first.")

        farmers = {}
        rate_moves = {}
        failed = []
        changed_entries = 0
        old_total = new_total = 0

        for row in self.farmer_billing_details:
            qty = flt(row.qty)
            old_rate = flt(row.rate)
            new_rate = old_rate
            try:
                entry = frappe.get_doc("Milk Entry", row.milk_entry)
                old_rate_doc = entry.milk_rate
                reprice_milk_entry(entry)          # in memory only
                new_rate = flt(entry.unit_price_with_incentive)
                if entry.milk_rate != old_rate_doc:
                    move = f"{old_rate_doc or '—'} → {entry.milk_rate}"
                    rate_moves[move] = rate_moves.get(move, 0) + 1
            except Exception as e:
                failed.append(f"{row.milk_entry}: {str(e)[:150]}")

            farmer = farmers.setdefault(row.farmer, {
                "farmer": row.farmer, "farmer_name": row.farmer_name,
                "qty": 0, "old_amount": 0, "new_amount": 0, "entries": 0,
            })
            farmer["qty"] += qty
            farmer["old_amount"] += qty * old_rate
            farmer["new_amount"] += qty * new_rate
            old_total += qty * old_rate
            new_total += qty * new_rate
            if flt(old_rate, 4) != flt(new_rate, 4):
                changed_entries += 1
                farmer["entries"] += 1

        rows = []
        for farmer in farmers.values():
            difference = flt(farmer["new_amount"] - farmer["old_amount"], 2)
            if not difference and not farmer["entries"]:
                continue
            rows.append({
                "farmer": farmer["farmer"],
                "farmer_name": farmer["farmer_name"],
                "entries": farmer["entries"],
                "qty": flt(farmer["qty"], 2),
                "old_rate": flt(farmer["old_amount"] / farmer["qty"], 2) if farmer["qty"] else 0,
                "new_rate": flt(farmer["new_amount"] / farmer["qty"], 2) if farmer["qty"] else 0,
                "old_amount": flt(farmer["old_amount"], 2),
                "new_amount": flt(farmer["new_amount"], 2),
                "difference": difference,
            })
        rows.sort(key=lambda r: -abs(r["difference"]))

        return {
            "changed_entries": changed_entries,
            "total_entries": len(self.farmer_billing_details),
            "changed_farmers": len(rows),
            "old_total": flt(old_total, 2),
            "new_total": flt(new_total, 2),
            "difference": flt(new_total - old_total, 2),
            "rate_moves": [f"{move} ({count} entries)" for move, count in rate_moves.items()],
            "rows": rows,
            "failed": failed[:5],
        }

    @frappe.whitelist()
    def recalculate_milk_rates(self):
        """
        Re-prices every Milk Entry in this billing from the Milk Rate that applies today,
        so a rate chart corrected after the entries were made can be applied without
        cancelling and re-creating entries. Only on a draft billing.

        Uses the same path a Milk Entry uses when it is saved (fixed farmer rate first,
        otherwise the rate chart), so an entry that is already correct stays untouched.
        """
        if self.docstatus != 0:
            frappe.throw("Rates can only be recalculated while the Farmer Billing is a draft.")
        if not self.farmer_billing_details:
            frappe.throw("Nothing to recalculate. Use 'Do Billing' first.")

        # Keep any hand-made adjustments; they are re-applied to the new amounts
        adjustments = {
            row.farmer: (flt(row.adjustment_amount), row.adjustment_reason)
            for row in self.farmer_billing_summary if flt(row.adjustment_amount)
        }
        old_total = flt(self.total_amount, 2)

        changed, failed, examples = 0, [], []
        for milk_entry in {row.milk_entry for row in self.farmer_billing_details if row.milk_entry}:
            try:
                entry = frappe.get_doc("Milk Entry", milk_entry)
                before = {f: entry.get(f) for f in REPRICED_FIELDS}
                reprice_milk_entry(entry)
                after = {f: entry.get(f) for f in REPRICED_FIELDS}

                updates = {f: after[f] for f in REPRICED_FIELDS if flt(before[f], 6) != flt(after[f], 6)
                           or (f == "milk_rate" and before[f] != after[f])}
                if not updates:
                    continue

                frappe.db.set_value("Milk Entry", milk_entry, updates)
                changed += 1
                if len(examples) < 5:
                    examples.append(
                        f"{milk_entry}: rate {flt(before['unit_price_with_incentive'], 2)} → "
                        f"{flt(after['unit_price_with_incentive'], 2)}"
                    )
            except Exception as e:
                failed.append(f"{milk_entry}: {str(e)[:200]}")
                frappe.log_error(
                    title=f"Farmer Billing {self.name}: re-pricing failed for {milk_entry}",
                    message=frappe.get_traceback(),
                )

        if not changed:
            frappe.msgprint(
                "Every Milk Entry already matches the current Milk Rate. Nothing changed."
                + (f"<br><br>{len(failed)} entry(s) could not be checked: {failed[0]}" if failed else ""),
                title="Rates Recalculated",
                indicator="blue" if not failed else "orange",
            )
            return

        # Rebuild the billing from the re-priced entries, then restore the adjustments
        self.get_milk_entry_detail_data()
        for row in self.farmer_billing_summary:
            if row.farmer in adjustments:
                adjustment, reason = adjustments[row.farmer]
                row.net_amount = flt(flt(row.amount) + adjustment, 2)
                row.adjustment_reason = reason
        self.set_adjustments()
        self.get_running_total()

        message = (
            f"<b>{changed}</b> Milk Entry(s) re-priced.<br>"
            f"Billing total {old_total} → <b>{flt(self.total_amount, 2)}</b><br><br>"
            + "<br>".join(examples)
            + (f"<br><br><b>{len(failed)}</b> failed: {failed[0]}" if failed else "")
        )
        self.add_comment("Comment", f"Rates recalculated: {changed} Milk Entry(s), "
                                    f"billing total {old_total} → {flt(self.total_amount, 2)}")
        frappe.msgprint(message, title="Rates Recalculated", indicator="orange" if failed else "green")

    # ================================================================== #
    # Team lead incentive — worked out in every billing, paid at month-end
    # ================================================================== #

    def get_incentive_settings(self):
        """Farmer Incentive Settings if the incentive applies to this billing, else None."""
        settings = frappe.get_cached_doc("Farmer Incentive Settings")
        if not settings.enabled or getdate(self.from_date) < getdate(settings.effective_from):
            return None
        return settings

    def is_month_end_billing(self):
        return getdate(self.to_date) == getdate(get_last_day(self.to_date))

    def set_team_lead_incentive(self):
        """
        Runs in Do Billing. Each farmer's litres in this billing go through the slabs and
        the incentive is added up under the farmer's team lead. Farmers are not paid this.
        """
        self.set("team_lead_incentive", [])
        for row in self.farmer_billing_summary:
            row.team_lead = None
            row.incentive_rate = row.incentive_amount = 0

        settings = self.get_incentive_settings()
        if not settings:
            return

        # Farmer's own Team Lead wins; otherwise the team lead of this DCS from settings
        team_lead_of = dict(frappe.get_all(
            "Supplier",
            filters={"name": ["in", [row.farmer for row in self.farmer_billing_summary]]},
            fields=["name", "custom_team_lead"],
            as_list=True,
        ))
        dcs_team_lead = next((r.team_lead for r in settings.dcs_team_leads if r.dcs == self.dcs), None)

        team_qty = {}
        for row in self.farmer_billing_summary:
            row.team_lead = team_lead_of.get(row.farmer) or dcs_team_lead
            if row.team_lead:
                team_qty[row.team_lead] = team_qty.get(row.team_lead, 0) + flt(row.qty, 2)

        teams = {}
        for row in self.farmer_billing_summary:
            if not row.team_lead:
                continue
            slab_qty = team_qty[row.team_lead] if settings.slab_based_on == "Team Total" else flt(row.qty, 2)
            row.incentive_rate = get_incentive_rate(slab_qty, settings.slabs)
            row.incentive_amount = flt(flt(row.qty, 2) * row.incentive_rate, 2)

            team = teams.setdefault(row.team_lead, {"members": 0, "qty": 0, "incentive_amount": 0})
            team["members"] += 1
            team["qty"] += flt(row.qty, 2)
            team["incentive_amount"] += row.incentive_amount

        team_lead_names = get_supplier_names(list(teams))
        for team_lead, team in teams.items():
            self.append("team_lead_incentive", {
                "team_lead": team_lead,
                "team_lead_name": team_lead_names.get(team_lead),
                "members": team["members"],
                "qty": team["qty"],
                "incentive_amount": flt(team["incentive_amount"], 2),
            })

        self.set_month_payout(settings)

        notes = []
        no_team_lead = [row.farmer for row in self.farmer_billing_summary if not row.team_lead]
        if no_team_lead:
            notes.append(
                f"{len(no_team_lead)} farmer(s) have no Team Lead (none on the farmer and none for this "
                f"DCS in Farmer Incentive Settings), so no incentive is worked out for them: "
                f"{', '.join(no_team_lead[:10])}" + (" ..." if len(no_team_lead) > 10 else "")
            )
        if self.is_month_end_billing():
            window_start = max(getdate(settings.effective_from), getdate(get_first_day(self.to_date)))
            window_end = getdate(add_days(self.from_date, -1))
            unbilled = window_start <= window_end and frappe.db.count("Milk Entry", {
                "dcs_id": self.dcs,
                "docstatus": 1,
                "status": ["!=", "Billed"],
                "date": ["between", [window_start, window_end]],
            })
            if unbilled:
                notes.append(
                    f"{unbilled} Milk Entries from earlier this month are not billed yet. Their "
                    "incentive is not in this payout; it will be paid at a later month-end once they are billed."
                )
        if notes:
            frappe.msgprint("<br><br>".join(notes), title="Team Lead Incentive", indicator="orange")

    def set_month_payout(self, settings=None):
        """
        Month-end billing only: payout per team lead = this billing's incentive plus every
        earlier billing of this DCS whose incentive is not paid yet. Runs in Do Billing
        (preview) and again in before_submit (final). Returns True if there is a payout run.
        """
        settings = settings or self.get_incentive_settings()
        # Drop payout-only rows from an earlier run; this billing's own team rows stay
        self.set("team_lead_incentive", [row for row in self.team_lead_incentive if row.members])
        for row in self.team_lead_incentive:
            row.month_incentive = 0
        self.flags.incentive_billings = []

        if not settings or not self.is_month_end_billing():
            return False

        self.flags.incentive_billings = frappe.get_all(
            "Farmer Billing",
            filters={
                "dcs": self.dcs,
                "docstatus": 1,
                "name": ["!=", self.name],
                "incentive_paid_in": ["is", "not set"],
                "from_date": [">=", settings.effective_from],
                "to_date": ["<=", self.to_date],
            },
            pluck="name",
        )

        earlier = {}
        if self.flags.incentive_billings:
            for r in frappe.get_all(
                "Farmer Billing Summary",
                filters={
                    "parenttype": "Farmer Billing",
                    "parent": ["in", self.flags.incentive_billings],
                    "team_lead": ["is", "set"],
                },
                fields=["team_lead", "incentive_amount"],
            ):
                earlier[r.team_lead] = earlier.get(r.team_lead, 0) + flt(r.incentive_amount)

        for row in self.team_lead_incentive:
            row.month_incentive = flt(flt(row.incentive_amount) + earlier.pop(row.team_lead, 0), 2)

        team_lead_names = get_supplier_names(list(earlier))
        for team_lead, amount in earlier.items():
            self.append("team_lead_incentive", {
                "team_lead": team_lead,
                "team_lead_name": team_lead_names.get(team_lead),
                "month_incentive": flt(amount, 2),
            })
        return True

    def mark_incentive_paid(self):
        """Earlier billings swept into this month-end payout are marked as paid by it."""
        for name in self.flags.incentive_billings or []:
            frappe.db.set_value("Farmer Billing", name, "incentive_paid_in", self.name, update_modified=False)

    # ================================================================== #
    # Layer 1 — Pre-validation (runs in before_submit)
    # ================================================================== #

    def validate_pi_creation_data(self):
        """
        Catch all predictable failures BEFORE any Purchase Invoice is created.
        If anything is wrong here, nothing is created. Clean error to the user.
        """
        errors = []

        if not self.farmer_billing_summary:
            frappe.throw("Farmer Billing Summary is empty. Use 'Do Billing' first.")
        if not self.farmer_billing_details:
            frappe.throw("Farmer Billing Details is empty. Use 'Do Billing' first.")

        # 1. Cross-check: every farmer in summary has detail rows
        summary_farmers = {fs.farmer for fs in self.farmer_billing_summary}
        detail_farmers = {fd.farmer for fd in self.farmer_billing_details}
        orphaned = summary_farmers - detail_farmers
        if orphaned:
            errors.append(
                f"No detail rows for farmer(s): {', '.join(sorted(orphaned))}"
            )

        # 2. Resolve & cache Dairy Settings item codes per milk type
        item_code_by_milk_type = {}
        used_milk_types = {fd.milk_type for fd in self.farmer_billing_details if fd.milk_type}
        for mt in used_milk_types:
            setting_key = MILK_TYPE_TO_SETTING.get(mt)
            if not setting_key:
                errors.append(f"Unknown milk type: {mt}")
                continue
            item_code = frappe.db.get_single_value("Dairy Settings", setting_key)
            if not item_code:
                errors.append(
                    f"Dairy Settings: '{setting_key}' is not set (needed for {mt} milk)"
                )
            else:
                item_code_by_milk_type[mt] = item_code

        # 3. Every detail row must have a Purchase Receipt link
        rows_missing_pr = [fd.milk_entry for fd in self.farmer_billing_details if not fd.purchase_receipt]
        if rows_missing_pr:
            errors.append(
                f"{len(rows_missing_pr)} detail row(s) have no Purchase Receipt link: "
                f"{', '.join(rows_missing_pr[:5])}"
                + (" ..." if len(rows_missing_pr) > 5 else "")
            )

        # 4. Bulk-check that every (PR, item_code) pair exists in Purchase Receipt Item
        pr_item_pairs = set()
        for fd in self.farmer_billing_details:
            if fd.purchase_receipt and fd.milk_type in item_code_by_milk_type:
                pr_item_pairs.add((fd.purchase_receipt, item_code_by_milk_type[fd.milk_type]))

        if pr_item_pairs:
            # Single query to find which pairs exist
            pr_list = list({p[0] for p in pr_item_pairs})
            existing_rows = frappe.db.get_all(
                "Purchase Receipt Item",
                filters={"parent": ["in", pr_list]},
                fields=["parent", "item_code"],
            )
            existing_pairs = {(r.parent, r.item_code) for r in existing_rows}

            missing = pr_item_pairs - existing_pairs
            if missing:
                sample = sorted(missing)[:5]
                errors.append(
                    f"{len(missing)} Purchase Receipt(s) missing expected item: "
                    + ", ".join(f"{pr}→{ic}" for pr, ic in sample)
                    + (" ..." if len(missing) > 5 else "")
                )

        # 5. Changed amounts need a usable adjustment account
        if any(flt(fs.adjustment_amount) for fs in self.farmer_billing_summary):
            adjustment_account = frappe.db.get_single_value("Dairy Settings", "custom_bill_adjustment_account")
            account = adjustment_account and frappe.db.get_value(
                "Account", adjustment_account, ["is_group", "disabled", "company"], as_dict=True
            )
            if not account or account.is_group or account.disabled:
                errors.append(
                    "Dairy Settings: 'Farmer Bill Adjustment Account' must be an enabled ledger account "
                    "(needed because some farmers' Net Amount was changed)"
                )
            elif account.company != self.company:
                errors.append(
                    f"Dairy Settings: 'Farmer Bill Adjustment Account' belongs to {account.company}, "
                    f"not {self.company}"
                )

        # 6. Team lead payout needs a usable incentive item and enabled team leads
        payout_team_leads = [r.team_lead for r in self.team_lead_incentive if flt(r.month_incentive) > 0]
        if payout_team_leads:
            incentive_item = frappe.db.get_single_value("Farmer Incentive Settings", "incentive_item")
            item = incentive_item and frappe.db.get_value(
                "Item", incentive_item, ["is_stock_item", "disabled"], as_dict=True
            )
            if not item or item.is_stock_item or item.disabled:
                errors.append("Farmer Incentive Settings: 'Incentive Item' must be an enabled, non-stock item")

            disabled = frappe.get_all(
                "Supplier", filters={"name": ["in", payout_team_leads], "disabled": 1}, pluck="name"
            )
            if disabled:
                errors.append(f"Team lead(s) are disabled: {', '.join(disabled)}")

        if errors:
            frappe.throw(
                "Cannot submit Farmer Billing — fix these issues first:<br><br>"
                + "<br>".join(f"• {e}" for e in errors),
                title="Pre-flight Validation Failed",
            )

    # ================================================================== #
    # PI Creation — idempotent, per-PI commit, error-tolerant
    # ================================================================== #

    def create_purchase_invoice(self):
        """
        Entry — Layer 1 defense: file lock prevents concurrent runs across tabs/users/workers.
        Only one process can run per Farmer Billing at any moment.
        """
        lock_name = f"farmer_billing_creation_{self.name}"
        try:
            with filelock(lock_name, timeout=2):
                self._do_create_purchase_invoice()
                self.create_team_lead_invoices()
        except LockTimeoutError:
            frappe.throw(
                "Invoice creation is already running for this Farmer Billing. "
                "Please wait for the current run to finish before retrying.",
                title="Already Running"
            )

    def _do_create_purchase_invoice(self):
        """
        Creates one Purchase Invoice per farmer. Each PI is its own DB transaction
        (commit per farmer) — releases row locks quickly, no lock-wait timeouts.
        Idempotent: re-running skips farmers who already have a PI for this billing.
        """
        total_farmers = len(self.farmer_billing_summary)

        # ---- LAYER 2A — Entry ceiling: exit immediately if already at/above expected ----
        current_count = frappe.db.count("Purchase Invoice", {
            "custom_farmer_billings": self.name,
            "docstatus": ["in", [0, 1]]
        })
        if current_count >= total_farmers:
            frappe.db.set_value("Farmer Billing", self.name, {
                "creation_status": "Completed",
                "creation_progress": f"{total_farmers} of {total_farmers} invoices created",
                "last_error": ""
            }, update_modified=False)
            frappe.db.commit()
            frappe.msgprint(
                f"All {total_farmers} invoices already exist for this billing. Nothing to create.",
                title="Already Complete",
                indicator="green"
            )
            return

        # Caches — populated lazily, reused across iterations
        adjustment_account = None  # Dairy Settings account for changed amounts
        item_code_cache = {}      # milk_type → item_code
        stock_uom_cache = {}      # item_code → stock_uom
        pr_item_cache = {}        # (purchase_receipt, item_code) → row dict

        receipts_to_complete = set()
        milk_entries_to_bill = set()

        created_count = 0
        failed_farmers = []

        # Move to "In Progress" so user can see something started
        frappe.db.set_value(
            "Farmer Billing", self.name,
            {"creation_status": "In Progress", "last_error": ""},
            update_modified=False,
        )
        frappe.db.commit()

        for idx, farmer_summary in enumerate(self.farmer_billing_summary, start=1):
            # ---- LAYER 2B — Loop ceiling: stop if we've hit the expected count ----
            current_count = frappe.db.count("Purchase Invoice", {
                "custom_farmer_billings": self.name,
                "docstatus": ["in", [0, 1]]
            })
            if current_count >= total_farmers:
                break

            farmer = farmer_summary.farmer

            # ---- LAYER 3 — Idempotency: skip if PI already exists for this billing + farmer ----
            existing_pi = frappe.db.exists("Purchase Invoice", {
                "custom_farmer_billings": self.name,
                "supplier": farmer,
                "docstatus": ("in", [0, 1]),
            })
            if existing_pi:
                created_count += 1
                # Still need to remember the entries/PRs for end-of-loop status updates
                for e in self.farmer_billing_details:
                    if e.farmer == farmer:
                        milk_entries_to_bill.add(e.milk_entry)
                        if e.purchase_receipt:
                            receipts_to_complete.add(e.purchase_receipt)
                continue

            try:
                purchase_inv = frappe.new_doc("Purchase Invoice")
                purchase_inv.supplier = farmer
                purchase_inv.posting_date = self.billing_date
                purchase_inv.set_posting_time = 1
                purchase_inv.due_date = self.due_date
                purchase_inv.custom_farmer_billings = self.name
                purchase_inv.company = self.company
                purchase_inv.custom_remark = farmer
                purchase_inv.cost_center = self.cost_center

                entries = [e for e in self.farmer_billing_details if e.farmer == farmer]

                for entry in entries:
                    # --- Cache: item_code from Dairy Settings (once per milk_type) ---
                    if entry.milk_type not in item_code_cache:
                        item_code_cache[entry.milk_type] = frappe.db.get_single_value(
                            "Dairy Settings", MILK_TYPE_TO_SETTING.get(entry.milk_type)
                        )
                    item_code = item_code_cache[entry.milk_type]

                    # --- Cache: stock_uom (once per item_code) ---
                    if item_code not in stock_uom_cache:
                        stock_uom_cache[item_code] = frappe.get_value(
                            "Item", item_code, "stock_uom"
                        )
                    stock_uom = stock_uom_cache[item_code]

                    # --- Cache: PR Item (once per (PR, item_code)) ---
                    cache_key = (entry.purchase_receipt, item_code)
                    if cache_key not in pr_item_cache:
                        pr_item_cache[cache_key] = frappe.db.get_value(
                            "Purchase Receipt Item",
                            {"parent": entry.purchase_receipt, "item_code": item_code},
                            ["name", "uom", "conversion_factor"], as_dict=True,
                        )
                    pr_item = pr_item_cache[cache_key]

                    milk_entries_to_bill.add(entry.milk_entry)
                    receipts_to_complete.add(entry.purchase_receipt)

                    purchase_inv.append("items", {
                        "item_code": item_code,
                        "received_qty": entry.qty,
                        "qty": entry.qty,
                        "uom": pr_item.uom,
                        "stock_uom": stock_uom,
                        "conversion_factor": pr_item.conversion_factor,
                        "rate": entry.rate,
                        "warehouse": self.dcs,
                        "purchase_receipt": entry.purchase_receipt,
                        "pr_detail": pr_item.name,
                        "fat": entry.fat_,
                        "snf": entry.snf_,
                        "milk_entry": entry.milk_entry,
                    })

                # Amount changed by hand on the billing: carry the difference as its own
                # charge row. ERPNext rejects negative item rates, and a charge row books
                # both directions against the adjustment account without touching valuation.
                # Measured against what the invoice actually carries, so the farmer is paid
                # exactly the Net Amount (invoice rows are rounded to paise one by one).
                # Row amounts are only worked out when the invoice is saved, so mirror the
                # same per-row rounding here to land exactly on the Net Amount.
                invoiced = sum(flt(flt(i.rate) * flt(i.qty), 2) for i in purchase_inv.items)
                adjustment = flt(
                    flt(farmer_summary.net_amount) - invoiced, 2
                ) if flt(farmer_summary.adjustment_amount) else 0
                if adjustment:
                    if adjustment_account is None:
                        adjustment_account = frappe.db.get_single_value(
                            "Dairy Settings", "custom_bill_adjustment_account"
                        )
                    purchase_inv.append("taxes", {
                        "charge_type": "Actual",
                        "category": "Total",
                        "add_deduct_tax": "Add" if adjustment > 0 else "Deduct",
                        "account_head": adjustment_account,
                        "cost_center": self.cost_center,
                        "description": f"Adjustment: {farmer_summary.adjustment_reason}",
                        "tax_amount": abs(adjustment),
                    })

                purchase_inv.save()
                purchase_inv.submit()

                # Commit per-PI — releases locks immediately
                frappe.db.commit()
                created_count += 1

                # Update progress so user sees it live
                frappe.db.set_value(
                    "Farmer Billing", self.name,
                    "creation_progress",
                    f"{created_count} of {total_farmers} invoices created",
                    update_modified=False,
                )
                frappe.db.commit()

            except Exception as e:
                # Roll back the failed PI; continue with next farmer
                frappe.db.rollback()
                failed_farmers.append({"farmer": farmer, "error": str(e)[:500]})
                frappe.log_error(
                    title=f"Farmer Billing {self.name}: PI failed for {farmer}",
                    message=frappe.get_traceback(),
                )

        # ---- Post-loop: dedup'd bulk updates ----
        # Update each PR once (status + per_billed in a single set_value call)
        for pr in receipts_to_complete:
            try:
                frappe.db.set_value("Purchase Receipt", pr, {
                    "status": "Completed",
                    "per_billed": "100",
                }, update_modified=False)
            except Exception:
                frappe.log_error(
                    title=f"Farmer Billing {self.name}: PR status update failed for {pr}",
                    message=frappe.get_traceback(),
                )

        # Mark Milk Entries Billed (one set_value each, no duplicates)
        for me in milk_entries_to_bill:
            try:
                frappe.db.set_value("Milk Entry", me, "status", "Billed", update_modified=False)
            except Exception:
                frappe.log_error(
                    title=f"Farmer Billing {self.name}: Milk Entry update failed for {me}",
                    message=frappe.get_traceback(),
                )

        # ---- Final status update ----
        if failed_farmers:
            status = "Partial" if created_count > 0 else "Failed"
            error_summary = "\n".join(
                f"{f['farmer']}: {f['error']}" for f in failed_farmers[:5]
            )
            if len(failed_farmers) > 5:
                error_summary += f"\n... and {len(failed_farmers) - 5} more"
            frappe.db.set_value("Farmer Billing", self.name, {
                "creation_status": status,
                "creation_progress": f"{created_count} of {total_farmers} invoices created",
                "last_error": error_summary,
            }, update_modified=False)
            frappe.db.commit()
            frappe.msgprint(
                f"<b>{created_count} of {total_farmers}</b> Purchase Invoice(s) created. "
                f"<b>{len(failed_farmers)}</b> failed.<br>"
                f"Use the <b>Retry Pending Invoices</b> button on this form to retry the failed ones "
                f"after fixing the issues. See <b>Last Error</b> field for details.",
                title="Partially Completed",
                indicator="orange",
            )
        else:
            frappe.db.set_value("Farmer Billing", self.name, {
                "creation_status": "Completed",
                "creation_progress": f"{created_count} of {total_farmers} invoices created",
                "last_error": "",
            }, update_modified=False)
            frappe.db.commit()
            frappe.msgprint(
                f"<b>{created_count}</b> Purchase Invoice(s) created successfully.",
                title="Completed",
                indicator="green",
            )

    def create_team_lead_invoices(self):
        """
        Month-end billing only. One Purchase Invoice per team lead with one row per billing
        being paid. Same pattern as the farmer invoices: commit per invoice, carry on after
        an error, and skip team leads that already have a live invoice (safe to retry).
        """
        pending = [
            row for row in self.team_lead_incentive
            if flt(row.month_incentive) > 0 and not (
                row.purchase_invoice
                and frappe.db.get_value("Purchase Invoice", row.purchase_invoice, "docstatus") in (0, 1)
            )
        ]
        if not pending:
            return

        incentive_item = frappe.db.get_single_value("Farmer Incentive Settings", "incentive_item")
        billings = {
            b.name: b for b in frappe.get_all(
                "Farmer Billing",
                filters={"incentive_paid_in": self.name, "docstatus": 1},
                fields=["name", "from_date", "to_date"],
            )
        }
        parts_by_team_lead = {}
        for r in frappe.get_all(
            "Farmer Billing Summary",
            filters={
                "parenttype": "Farmer Billing",
                "parent": ["in", list(billings)],
                "team_lead": ["is", "set"],
                "incentive_amount": [">", 0],
            },
            fields=["parent", "team_lead", "count(name) as members", "sum(qty) as qty",
                    "sum(incentive_amount) as amount"],
            group_by="parent, team_lead",
        ):
            parts_by_team_lead.setdefault(r.team_lead, []).append(r)

        created_count = 0
        failed = []
        for row in pending:
            try:
                parts = sorted(
                    parts_by_team_lead.get(row.team_lead, []),
                    key=lambda p: getdate(billings[p.parent].from_date),
                )
                if flt(sum(flt(p.amount) for p in parts), 2) != flt(row.month_incentive, 2):
                    frappe.throw(
                        f"Payout {row.month_incentive} does not match the billings being paid "
                        f"({flt(sum(flt(p.amount) for p in parts), 2)})."
                    )

                purchase_inv = frappe.new_doc("Purchase Invoice")
                purchase_inv.supplier = row.team_lead
                purchase_inv.posting_date = self.billing_date
                purchase_inv.set_posting_time = 1
                purchase_inv.due_date = self.due_date
                purchase_inv.company = self.company
                purchase_inv.cost_center = self.cost_center
                purchase_inv.custom_remark = row.team_lead
                purchase_inv.remarks = f"Team lead incentive paid by Farmer Billing {self.name}"

                for p in parts:
                    billing = billings[p.parent]
                    purchase_inv.append("items", {
                        "item_code": incentive_item,
                        "qty": 1,
                        "rate": flt(p.amount, 2),
                        "cost_center": self.cost_center,
                        "description": (
                            f"Team lead incentive {formatdate(billing.from_date)} to "
                            f"{formatdate(billing.to_date)}: {p.members} member(s), "
                            f"{flt(p.qty, 2)} L ({billing.name})"
                        ),
                    })

                purchase_inv.save()
                purchase_inv.submit()
                frappe.db.set_value(
                    "Farmer Billing Team Incentive", row.name,
                    "purchase_invoice", purchase_inv.name, update_modified=False,
                )
                # Commit per-PI, together with its link on the team row
                frappe.db.commit()
                row.purchase_invoice = purchase_inv.name
                created_count += 1

            except Exception as e:
                frappe.db.rollback()
                failed.append(f"{row.team_lead}: {str(e)[:300]}")
                frappe.log_error(
                    title=f"Farmer Billing {self.name}: team lead PI failed for {row.team_lead}",
                    message=frappe.get_traceback(),
                )

        if failed:
            last_error = frappe.db.get_value("Farmer Billing", self.name, "last_error")
            frappe.db.set_value("Farmer Billing", self.name, {
                "creation_status": "Partial",
                "last_error": (f"{last_error}\n" if last_error else "")
                + "Team lead invoices:\n" + "\n".join(failed[:5])
                + (f"\n... and {len(failed) - 5} more" if len(failed) > 5 else ""),
            }, update_modified=False)
            frappe.db.commit()
            frappe.msgprint(
                f"<b>{created_count}</b> team lead Purchase Invoice(s) created, <b>{len(failed)}</b> failed. "
                f"Use <b>Retry Pending Invoices</b> after fixing the issues. See <b>Last Error</b>.",
                title="Team Lead Incentive",
                indicator="orange",
            )
        else:
            frappe.msgprint(
                f"<b>{created_count}</b> team lead Purchase Invoice(s) created.",
                title="Team Lead Incentive",
                indicator="green",
            )

    @frappe.whitelist()
    def retry_pending_invoices(self):
        """
        Button method. Re-runs PI creation.
        Idempotency check inside create_purchase_invoice() automatically skips
        farmers who already have a PI for this billing.
        """
        if self.docstatus != 1:
            frappe.throw("Farmer Billing must be submitted before retrying.")
        self.create_purchase_invoice()

    # ================================================================== #
    # Cancel flow
    # ================================================================== #

    def before_cancel(self):
        if self.incentive_paid_in and self.incentive_paid_in != self.name:
            frappe.throw(
                f"The team lead incentive of this billing was paid by Farmer Billing "
                f"<b>{self.incentive_paid_in}</b>. Cancel that billing first.",
                title="Incentive Already Paid",
            )

    def on_cancel(self):
        self.cancel_team_lead_invoices()

        purchase_invoices = frappe.get_list(
            "Purchase Invoice",
            filters={"custom_farmer_billings": self.name},
            pluck="name",
        )

        if not purchase_invoices:
            frappe.msgprint("No linked Purchase Invoices found.")
            return

        for pi_name in purchase_invoices:
            pi_doc = frappe.get_doc("Purchase Invoice", pi_name)
            if pi_doc.docstatus == 1:
                try:
                    pi_doc.cancel()
                    frappe.msgprint(f"Purchase Invoice {pi_name} has been cancelled.")
                except Exception as e:
                    frappe.log_error(frappe.get_traceback(), f"Failed to cancel Purchase Invoice {pi_name}")
                    frappe.throw(f"Error cancelling Purchase Invoice {pi_name}: {str(e)}")

    def cancel_team_lead_invoices(self):
        for row in self.team_lead_incentive:
            if row.purchase_invoice and frappe.db.get_value("Purchase Invoice", row.purchase_invoice, "docstatus") == 1:
                frappe.get_doc("Purchase Invoice", row.purchase_invoice).cancel()
                frappe.msgprint(f"Team lead Purchase Invoice {row.purchase_invoice} has been cancelled.")

        # Billings this one paid become payable again at the next month-end
        for name in frappe.get_all(
            "Farmer Billing",
            filters={"incentive_paid_in": self.name, "name": ["!=", self.name]},
            pluck="name",
        ):
            frappe.db.set_value("Farmer Billing", name, "incentive_paid_in", None, update_modified=False)


def get_supplier_names(suppliers):
    if not suppliers:
        return {}
    return dict(frappe.get_all(
        "Supplier", filters={"name": ["in", suppliers]}, fields=["name", "supplier_name"], as_list=True
    ))


# Fields the dairy app's pricing writes; compared before/after to see what a re-price changed
REPRICED_FIELDS = (
    "milk_rate", "unit_price", "incentive", "incentive_per", "unit_price_with_incentive",
    "fat_deduction", "fat_deduction_per", "snf_deduction", "snf_deduction_per", "total",
)


def reprice_milk_entry(entry):
    """Price a Milk Entry the same way Milk Entry.before_save does, in memory."""
    farmer = frappe.get_cached_value(
        "Supplier", entry.member, ["custom_fixed_rate", "custom_apply_fixed_rate"], as_dict=True
    ) if entry.member else None

    if farmer and farmer.custom_apply_fixed_rate and flt(farmer.custom_fixed_rate) > 0:
        entry.unit_price_with_incentive = farmer.custom_fixed_rate
        entry.total = flt(entry.unit_price_with_incentive) * flt(entry.volume)
        return

    entry.get_pricelist()
