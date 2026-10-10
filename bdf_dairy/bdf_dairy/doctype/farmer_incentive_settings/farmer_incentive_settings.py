# Copyright (c) 2026, BDF and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class FarmerIncentiveSettings(Document):
    def validate(self):
        self.slabs.sort(key=lambda s: flt(s.above_qty))
        for idx, slab in enumerate(self.slabs, start=1):
            slab.idx = idx

        seen = set()
        for row in self.dcs_team_leads:
            if row.dcs in seen:
                frappe.throw(f"DCS Team Leads row {row.idx}: <b>{row.dcs}</b> is listed more than once.")
            seen.add(row.dcs)

        if not self.enabled:
            return

        if not self.effective_from:
            frappe.throw("Set the Effective From date.")
        if not self.incentive_item:
            frappe.throw("Set the Incentive Item.")
        if not self.slabs:
            frappe.throw("Add at least one slab.")

        validate_incentive_item(self.incentive_item)

        # Slabs must start at 0 and run end-to-end with no gaps or overlaps
        if flt(self.slabs[0].above_qty) != 0:
            frappe.throw("The first slab must start Above 0 litres.")

        for i, slab in enumerate(self.slabs):
            is_last = i == len(self.slabs) - 1
            if not flt(slab.up_to_qty):
                if not is_last:
                    frappe.throw(f"Row {slab.idx}: only the last slab can have no upper limit.")
            elif flt(slab.up_to_qty) <= flt(slab.above_qty):
                frappe.throw(f"Row {slab.idx}: Up To must be more than Above.")

            if i and flt(slab.above_qty) != flt(self.slabs[i - 1].up_to_qty):
                frappe.throw(
                    f"Row {slab.idx}: Above must equal the previous slab's Up To "
                    f"({flt(self.slabs[i - 1].up_to_qty)}) so there are no gaps."
                )


def validate_incentive_item(item_code):
    item = frappe.db.get_value("Item", item_code, ["is_stock_item", "disabled"], as_dict=True)
    if not item:
        frappe.throw(f"Incentive Item <b>{item_code}</b> does not exist.")
    if item.is_stock_item:
        frappe.throw(f"Incentive Item <b>{item_code}</b> must be a non-stock item.")
    if item.disabled:
        frappe.throw(f"Incentive Item <b>{item_code}</b> is disabled.")


def get_incentive_rate(qty, slabs):
    """Rate per litre for the slab that `qty` falls in (above < qty <= up_to)."""
    qty = flt(qty)
    for slab in slabs:
        if qty > flt(slab.above_qty) and (not flt(slab.up_to_qty) or qty <= flt(slab.up_to_qty)):
            return flt(slab.rate)
    return 0
