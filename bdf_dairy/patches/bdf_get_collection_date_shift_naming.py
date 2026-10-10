import frappe


def execute():
	"""BDF Get Collection is now one document per date + shift (BGC-{date}-{shift}).
	Remove the Customize Form overrides that named it per warehouse and listed the legacy fields."""
	frappe.db.delete(
		"Property Setter",
		{"doc_type": "BDF Get Collection", "property": ["in", ["autoname", "naming_rule"]]},
	)
	frappe.db.delete(
		"Property Setter",
		{
			"doc_type": "BDF Get Collection",
			"field_name": ["in", ["warehouse", "mpp_code"]],
			"property": "in_list_view",
		},
	)
	frappe.clear_cache(doctype="BDF Get Collection")
