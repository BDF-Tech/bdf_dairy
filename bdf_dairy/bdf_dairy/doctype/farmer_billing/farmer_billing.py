# Copyright (c) 2025, BDF and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils.synchronization import filelock


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
        # Layer 1 — catch all predictable issues BEFORE any PI is created
        self.validate_pi_creation_data()
        self.creation_status = "Pending"

    def on_submit(self):
        # Per-PI atomic commit. Idempotent. Continues on per-farmer error.
        self.create_purchase_invoice()

    def before_save(self):
        self.get_running_total()

    def get_running_total(self):
        total_qty, total_amount = 0, 0
        for row in self.farmer_billing_summary:
            total_qty += row.qty
            total_amount += row.amount

        self.total_qty = total_qty
        self.average_rate = (total_amount / total_qty) if total_qty else 0
        self.total_amount = total_amount

    @frappe.whitelist()
    def get_milk_entry_detail_data(self):
        self.farmer_billing_details.clear()
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
            })
        self.get_running_total()

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
        except TimeoutError:
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

    def on_cancel(self):
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
