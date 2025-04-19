app_name = "bdf_dairy"
app_title = "BDF Dairy"
app_publisher = "BDF"
app_description = "BDF"
app_email = "info@bastardairyfarm.com"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/bdf_dairy/css/bdf_dairy.css"
# app_include_js = "/assets/bdf_dairy/js/bdf_dairy.js"

# include js, css files in header of web template
# web_include_css = "/assets/bdf_dairy/css/bdf_dairy.css"
# web_include_js = "/assets/bdf_dairy/js/bdf_dairy.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "bdf_dairy/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"Stock Entry" : "public/js/stock_entry.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "bdf_dairy.utils.jinja_methods",
# 	"filters": "bdf_dairy.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "bdf_dairy.install.before_install"
# after_install = "bdf_dairy.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "bdf_dairy.uninstall.before_uninstall"
# after_uninstall = "bdf_dairy.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "bdf_dairy.utils.before_app_install"
# after_app_install = "bdf_dairy.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "bdf_dairy.utils.before_app_uninstall"
# after_app_uninstall = "bdf_dairy.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "bdf_dairy.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"bdf_dairy.tasks.all"
# 	],
# 	"daily": [
# 		"bdf_dairy.tasks.daily"
# 	],
# 	"hourly": [
# 		"bdf_dairy.tasks.hourly"
# 	],
# 	"weekly": [
# 		"bdf_dairy.tasks.weekly"
# 	],
# 	"monthly": [
# 		"bdf_dairy.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "bdf_dairy.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "bdf_dairy.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "bdf_dairy.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["bdf_dairy.utils.before_request"]
# after_request = ["bdf_dairy.utils.after_request"]

# Job Events
# ----------
# before_job = ["bdf_dairy.utils.before_job"]
# after_job = ["bdf_dairy.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"bdf_dairy.auth.validate"
# ]
fixtures = [
    {
        "doctype": "Server Script",
        "filters": [
            ["name", "in", ["Validate WO to Syock Entry", 
                            "Cancel Farmer Bill Invoice",
                            "Restrict And Update Automatic Rate", 
                            "Process Loss Handling For Work Order", 
                            "Restrict To Create Multiple Sales Invoice", 
                            "Sales Invoice Minimum Order Quantity Validation", 
                            "Sales Order Minimum Order Quantity Validation"]],
        ],
    },
    {
        "doctype": "Client Script",
        "filters": [
            ["name", "in", ["Restrict For Multiple Sales Invoice", "Purchase Order Item Wise Accepted Warehouse", "Purchase Receipt Item Wise Accepted Warehouse", "Purchase Invoice Item Wise Accepted Warehouse"]],
        ],
    },
    {
        "doctype": "Stock Entry Type",
        "filters": [
            ["name", "in", ["Material Transfer For Gate Pass"]],
        ],
    },
    {
        "doctype": "Custom Field",
        "filters": [
            ["name","in",["Purchase Invoice-custom_farmer_billings"]]
        ]    
    }
]