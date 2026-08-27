app_name = "ai_hr"
app_title = "AI HR"
app_publisher = "Kabila Ngimba"
app_description = "AI-powered ATS and recruitment platform extending Frappe HR"
app_email = "kabilangimba2000@gmail.com"
app_license = "mit"

# Send non-GET requests for this app's endpoints as native `application/json`
# bodies instead of form-encoded, per-key JSON-stringified values.
use_json_request_body = True

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "ai_hr",
# 		"logo": "/assets/ai_hr/logo.png",
# 		"title": "AI HR",
# 		"route": "/ai_hr",
# 		"has_permission": "ai_hr.api.permission.has_app_permission",
# 	}
# ]

# Companion apps that extend a host app (instead of taking their own apps-screen icon) can pin
# their workspaces into the host app's workspace dock (rail) with this hook. Declaring it keeps
# the app off the apps screen, so it takes precedence over any add_to_apps_screen above. Who can
# see a pinned workspace is controlled by that workspace's own Roles table.
# add_to_workspace_dock = [
# 	{
# 		"app": "erpnext",
# 		"workspace": "My Workspace",
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/ai_hr/css/ai_hr.css"
# app_include_js = "/assets/ai_hr/js/ai_hr.js"

# include js, css files in header of web template
# web_include_css = "/assets/ai_hr/css/ai_hr.css"
# web_include_js = "/assets/ai_hr/js/ai_hr.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "ai_hr/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# app_include_css = "/assets/ai_hr/css/ai_hr_dashboard.css"


# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "ai_hr/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Setup Wizard
# ------------

# open a fresh site's setup in this app's own UI instead of the desk wizard.
# must be a non-desk route (not under /desk or /app); to customize setup within
# desk, use setup_wizard_stages / setup_wizard_complete instead.
# setup_wizard_url = "/ai_hr/setup"

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "ai_hr.utils.jinja_methods",
# 	"filters": "ai_hr.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "ai_hr.install.before_install"
# after_install = "ai_hr.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "ai_hr.uninstall.before_uninstall"
# after_uninstall = "ai_hr.uninstall.after_uninstall"

# Disable / Enable
# ----------------
# Called when this app is logically disabled or re-enabled on a site,
# without uninstalling it. Use this to hide/restore fields this app adds
# to other apps' doctypes.

# before_disable = "ai_hr.uninstall.before_disable"
# after_disable = "ai_hr.uninstall.after_disable"
# before_enable = "ai_hr.install.before_enable"
# after_enable = "ai_hr.install.after_enable"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "ai_hr.utils.before_app_install"
# after_app_install = "ai_hr.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "ai_hr.utils.before_app_uninstall"
# after_app_uninstall = "ai_hr.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "ai_hr.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "ai_hr.notifications.get_notification_config"

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
# 		"ai_hr.tasks.all"
# 	],
# 	"daily": [
# 		"ai_hr.tasks.daily"
# 	],
# 	"hourly": [
# 		"ai_hr.tasks.hourly"
# 	],
# 	"weekly": [
# 		"ai_hr.tasks.weekly"
# 	],
# 	"monthly": [
# 		"ai_hr.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "ai_hr.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "ai_hr.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "ai_hr.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "ai_hr.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["ai_hr.utils.before_request"]
# after_request = ["ai_hr.utils.after_request"]

# Job Events
# ----------
# before_job = ["ai_hr.utils.before_job"]
# after_job = ["ai_hr.utils.after_job"]

# after_file_upload = ["ai_hr.utils.after_file_upload"]

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
# 	"ai_hr.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
export_python_type_annotations = True

# Require all whitelisted methods to have type annotations
require_type_annotated_api_methods = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

# ---------------------------------------------------------------------------
# AI HR

# Brand logo used by the login page, navbar and email templates.
# Generated from the supplied SCI LOGO artwork: trimmed of its white margin and
# converted to a transparent PNG, so it sits correctly on any background.
app_logo_url = "/assets/ai_hr/images/starrich-logo.png"

# Branded landing screen shown after login (the /app/desktop apps page).
#
# These load on every Desk page, which is the only hook Frappe offers - so both
# are written to stay inert elsewhere: the CSS is scoped entirely under
# `body.apps-page` (a class desk.js sets only for the apps grid), and the JS just
# registers one listener for the `desktop_screen` event that page emits.
# Declared as bundles, not raw /assets paths, so esbuild gives each build a
# content-hashed filename. Frappe's bundled_asset() only rewrites a path when it
# contains ".bundle." AND does not already start with /assets - a literal
# /assets/... URL is emitted verbatim, and since assets are served with
# `max-age=43200` the browser then keeps a stale copy for 12 hours.
# Website-side styles (the Starrich footer). Bundled for the same cache-busting
# reason as the desk assets below.
web_include_css = "starrich_web.bundle.css"

app_include_css = "ai_hr_desktop.bundle.css"
app_include_js = "ai_hr_desktop.bundle.js"

# Desk boot splash and browser favicon. erpnext sets these in its own
# website_context; ai_hr loads after erpnext, so these win.
website_context = {
	"splash_image": "/assets/ai_hr/images/starrich-logo.png",
	# The star alone: the full lockup is ~3.5:1, and shrunk into a 32px tab
	# icon it is an unreadable smear.
	"favicon": "/assets/ai_hr/images/starrich-icon.png",
}
# ---------------------------------------------------------------------------

# Rebrands the "Frappe HR" label that hrms hard-codes into its apps-screen hook.
# See ai_hr/boot.py for why this is done at boot rather than per surface.
extend_bootinfo = "ai_hr.boot.boot_session"

after_install = "ai_hr.setup.after_install"

# Re-assert custom fields on every migrate so the schema converges on deploy.
after_migrate = "ai_hr.setup.after_migrate"

doc_events = {
	"Job Applicant": {
		"validate": "ai_hr.setup.sync_status_from_stage",
		# Parse the CV as soon as an application arrives, including from the
		# public web form. The handler never raises and does no inline work, so a
		# candidate's submission cannot be slowed or broken by the AI side.
		"after_insert": "ai_hr.api.resume.auto_parse_on_insert",
	},
}


# NOTE: `webform_include_css` is deliberately not used. Frappe only consults
# that hook when a <web_form_name>.css already exists beside the web form
# module, and hrms ships none for job_application - so the hook can never
# fire. The stylesheet is applied to the form's own `custom_css` field by
# ai_hr.setup.style_job_application_form() instead.

doctype_js = {
	"Job Applicant": "public/js/job_applicant.js",
	"Job Opening": "public/js/job_opening.js",
	"AI Interview": "public/js/ai_interview.js",
}
