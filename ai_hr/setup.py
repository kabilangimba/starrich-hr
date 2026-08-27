"""Custom fields installed onto core HRMS DocTypes.

Everything here is additive. HRMS and Frappe source is never edited (§13, §23),
so `bench update` cannot clobber this app's changes and this app cannot break
stock HRMS behaviour.
"""

from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

#: The ATS pipeline from §9.
#:
#: This is a *separate* field from the stock `Job Applicant.status`, which is a
#: fixed 6-value Select owned by HRMS. Widening that Select would mean editing
#: core, so the richer pipeline lives here and `STAGE_TO_STATUS` keeps the stock
#: field in step - existing HRMS reports and workflows keep working untouched.
ATS_STAGES = [
	"Applied",
	"CV Screening",
	"AI Screening",
	"Shortlisted",
	"Phone Interview",
	"Technical Interview",
	"Final Interview",
	"Offer",
	"Hired",
	"Rejected",
	"Withdrawn",
	"On Hold",
]

#: Maps each ATS stage onto the nearest stock status value.
STAGE_TO_STATUS = {
	"Applied": "Open",
	"CV Screening": "Open",
	"AI Screening": "Open",
	"Shortlisted": "Shortlisted",
	"Phone Interview": "Shortlisted",
	"Technical Interview": "Shortlisted",
	"Final Interview": "Shortlisted",
	"Offer": "Accepted",
	"Hired": "Accepted",
	"Rejected": "Rejected",
	"Withdrawn": "Rejected",
	"On Hold": "Hold",
}


def get_custom_fields() -> dict[str, list[dict]]:
	return {
		"Job Applicant": [
			{
				"fieldname": "ai_hr_section",
				"fieldtype": "Section Break",
				"label": "AI HR",
				"insert_after": "status",
				"collapsible": 0,
			},
			{
				"fieldname": "ats_stage",
				"fieldtype": "Select",
				"label": "ATS Stage",
				"options": "\n".join(ATS_STAGES),
				"default": "Applied",
				"insert_after": "ai_hr_section",
				"in_standard_filter": 1,
				"in_list_view": 1,
				"description": "Recruitment pipeline stage. Keeps the standard Status field in sync.",
			},
			{
				"fieldname": "ai_match_score",
				"fieldtype": "Percent",
				"label": "AI Match Score",
				"insert_after": "ats_stage",
				"read_only": 1,
				"in_list_view": 1,
				"description": "Advisory only. The recruiter makes the decision.",
			},
			{"fieldname": "ai_hr_cb", "fieldtype": "Column Break", "insert_after": "ai_match_score"},
			{
				"fieldname": "ai_resume_analysis",
				"fieldtype": "Link",
				"label": "Resume Analysis",
				"options": "AI Resume Analysis",
				"insert_after": "ai_hr_cb",
				"read_only": 1,
			},
			{
				"fieldname": "ai_parsing_status",
				"fieldtype": "Data",
				"label": "CV Parsing Status",
				"insert_after": "ai_resume_analysis",
				"read_only": 1,
			},
		],
		# Job Opening carries only a free-text `description`, so structured
		# requirements needed for matching live in app-owned fields.
		"Job Opening": [
			{
				"fieldname": "ai_hr_req_section",
				"fieldtype": "Section Break",
				"label": "AI HR Requirements",
				"insert_after": "description",
				"collapsible": 1,
				"description": "Structured requirements used for AI candidate matching.",
			},
			{
				"fieldname": "ai_required_skills",
				"fieldtype": "Table",
				"label": "Required Skills",
				"options": "AI Job Skill",
				"insert_after": "ai_hr_req_section",
			},
			{
				"fieldname": "ai_min_experience",
				"fieldtype": "Float",
				"label": "Minimum Years of Experience",
				"insert_after": "ai_required_skills",
				"precision": "1",
			},
			{
				"fieldname": "ai_hr_req_cb",
				"fieldtype": "Column Break",
				"insert_after": "ai_min_experience",
			},
			{
				"fieldname": "ai_education_requirement",
				"fieldtype": "Small Text",
				"label": "Education Requirement",
				"insert_after": "ai_hr_req_cb",
			},
		],
	}


def after_install() -> None:
	create_custom_fields(get_custom_fields(), ignore_validate=True)
	frappe.db.commit()


def after_migrate() -> None:
	"""Re-assert custom fields after every migrate.

	HRMS installs its own custom fields from `after_install` only, which is why a
	half-finished install leaves them missing with no way to self-heal. Running
	this on migrate as well makes the app's schema converge on every deploy;
	`create_custom_fields` is idempotent, so this is safe to repeat.
	"""
	after_install()
	mount_in_frappe_hr()
	style_job_application_form()
	use_starrich_footer()
	apply_brand_assets()
	install_dashboards()
	disable_inapplicable_reports()
	grant_hr_read_access()
	hide_navbar_items()
	restrict_workspaces()


# -- workspace access ---------------------------------------------------------

#: Standard workspaces restricted to a role, as {workspace: required role}.
#:
#: "Build" is Frappe's developer workspace -- it links Dashboard, Report and
#: Module Def, which are framework-authoring tools, not HR features. It ships
#: with no roles at all, so by default every desk user sees it; HR staff land on
#: it and find doctypes they have no business editing.
#:
#: Gating by role rather than hiding outright keeps it reachable for admins.
#: Note this restricts *the workspace*, not the doctypes: HR keeps read on
#: Report, which is what lets them actually run the HR reports.
RESTRICTED_WORKSPACES = {"Build": "System Manager"}


def restrict_workspaces() -> None:
	"""Gate developer-facing standard workspaces behind a role. Idempotent.

	Applied as a Workspace Customization rather than by editing the Workspace: a
	standard workspace is re-synced from its app's JSON on every migrate, which
	would drop a direct edit. The customization is the sanctioned delta and is
	merged over the live base at read time.
	"""
	if not frappe.db.exists("DocType", "Workspace Customization"):
		return

	for workspace, role in RESTRICTED_WORKSPACES.items():
		if not frappe.db.exists("Workspace", workspace):
			continue

		# Only app-shipped workspaces may be customized; the doctype enforces this.
		if not frappe.db.get_value("Workspace", workspace, "standard"):
			continue

		if frappe.db.exists("Workspace Customization", workspace):
			doc = frappe.get_doc("Workspace Customization", workspace)
		else:
			doc = frappe.new_doc("Workspace Customization")
			doc.workspace = workspace

		if role in {r.role for r in doc.added_roles}:
			continue

		doc.append("added_roles", {"role": role})
		doc.save(ignore_permissions=True)

	frappe.clear_cache()
	frappe.db.commit()


def sync_status_from_stage(doc, method=None) -> None:
	"""Keep the stock `status` field aligned with `ats_stage`.

	Hooked on Job Applicant validate. Only writes when the mapped value actually
	differs, so a recruiter editing `status` directly is not fought on every save.
	"""
	stage = getattr(doc, "ats_stage", None)
	if not stage:
		return

	mapped = STAGE_TO_STATUS.get(stage)
	if mapped and doc.status != mapped:
		doc.status = mapped


# -- Frappe HR integration ----------------------------------------------------
#
# The Frappe HR app dock lists workspaces whose `app` is "hrms". A workspace
# created by this app defaults to app="ai_hr", which puts it in its own dock
# instead of alongside Recruitment, Payroll and Leaves. Mounting it on "hrms"
# is what makes AI HR appear inside Frappe HR (its module stays "AI HR", so
# ownership and `bench uninstall-app` behaviour are unchanged).

HR_APP = "hrms"
WORKSPACE = "AI HR"

#: Sits immediately after Recruitment (3) and before Leaves (5).
WORKSPACE_SEQUENCE = 4.5

#: Sidebar entries, as (type, label, link_type, link_to, icon).
#:
#: `group` renders a collapsible heading and everything after it, until the next
#: group, is nested beneath it. That is the shape Frappe's own sidebars use: a
#: "Section Break" row with indent=1, then Link rows with child=1 (see the
#: Payments sidebar for the reference pattern).
#:
#: Icons are verified against the v17 lucide sprite.
SIDEBAR_ITEMS = [
	("group", "AI HR", None, None, None),
	("link", "AI HR Settings", "DocType", "AI HR Settings", "settings"),

	("group", "Recruitment AI", None, None, None),
	# Job descriptions are generated from the Job Opening form, so the list is
	# the entry point rather than a page of its own.
	("link", "AI Job Description", "DocType", "Job Opening", "file-text"),
	("link", "AI Resume Analysis", "DocType", "AI Resume Analysis", "file-search"),
	("link", "AI Candidate Score", "DocType", "AI Candidate Score", "target"),
	# Matching is run against candidates, so this opens the candidate list.
	("link", "AI Candidate Matching", "DocType", "Job Applicant", "users"),
	("link", "Candidate Ranking", "Report", "Candidate Ranking", "list-ordered"),
	("link", "AI Interview Assistant", "DocType", "AI Interview", "message-square"),
	("link", "AI Skill Gap Analysis", "Report", "AI Skill Gap Analysis", "chart-no-axes-gantt"),

	# Root-level, not part of a group - "toplink" keeps child=0 so it is not
	# nested under the preceding "Recruitment AI" heading.
	("toplink", "AI Recruiter Assistant", "Page", "ai-recruiter", "sparkles"),

	("group", "Reports", None, None, None),
	("link", "Candidate Analytics", "Report", "Candidate Analytics", "chart-pie"),
	("link", "Hiring Analytics", "Report", "Hiring Analytics", "chart-line"),
]


def mount_in_frappe_hr() -> None:
	"""Make the AI HR workspace appear inside the Frappe HR app.

	Idempotent, and safe to run on every migrate: Frappe only auto-derives
	`Workspace.app` from the module when the field is empty, so an explicit
	"hrms" survives.
	"""
	if not frappe.db.exists("Workspace", WORKSPACE):
		return

	if HR_APP not in frappe.get_installed_apps():
		# Nothing to mount onto - leave the workspace in its own dock.
		return

	workspace = frappe.get_doc("Workspace", WORKSPACE)
	if workspace.app != HR_APP or workspace.sequence_id != WORKSPACE_SEQUENCE:
		workspace.app = HR_APP
		workspace.sequence_id = WORKSPACE_SEQUENCE
		workspace.save(ignore_permissions=True)

	_sync_sidebar()
	_sync_desktop_icon()
	frappe.db.commit()


def _sync_sidebar() -> None:
	"""Create or refresh the Workspace Sidebar entry shown in the HR dock."""
	if not frappe.db.exists("DocType", "Workspace Sidebar"):
		return  # older Frappe without the sidebar doctype

	if frappe.db.exists("Workspace Sidebar", WORKSPACE):
		sidebar = frappe.get_doc("Workspace Sidebar", WORKSPACE)
	else:
		sidebar = frappe.new_doc("Workspace Sidebar")
		sidebar.name = WORKSPACE

	sidebar.title = WORKSPACE
	sidebar.header_icon = "sparkles"
	sidebar.app = HR_APP
	sidebar.module = "AI HR"
	sidebar.standard = 1

	# Rebuild the item list so renamed or removed links cannot linger.
	sidebar.set("items", [])
	for kind, label, link_type, link_to, icon in SIDEBAR_ITEMS:
		if kind == "group":
			sidebar.append(
				"items",
				{"type": "Section Break", "label": label, "indent": 1, "collapsible": 1},
			)
			continue

		# Skip anything not installed yet rather than writing a dangling link -
		# a broken link_to is what makes a whole sidebar fail to render.
		if not _link_target_exists(link_type, link_to):
			continue

		sidebar.append(
			"items",
			{
				"type": "Link",
				"label": label,
				"link_type": link_type,
				"link_to": link_to,
				"icon": icon,
				# "link" nests under the preceding group heading; "toplink" stays
				# at root level.
				"child": 1 if kind == "link" else 0,
				"collapsible": 1,
			},
		)

	_drop_empty_groups(sidebar)

	if sidebar.is_new():
		sidebar.insert(ignore_permissions=True)
	else:
		sidebar.save(ignore_permissions=True)


def _link_target_exists(link_type: str, link_to: str) -> bool:
	if link_type in ("DocType", "Report", "Page"):
		return bool(frappe.db.exists(link_type, link_to))
	return True


def _drop_empty_groups(sidebar) -> None:
	"""Remove a heading whose links were all skipped.

	A group with nothing under it renders as a dead label, which looks like a
	broken menu rather than a feature that is not installed.
	"""
	items = sidebar.get("items")
	keep = []
	for i, item in enumerate(items):
		if item.type == "Section Break":
			following = items[i + 1 :]
			has_child = False
			for nxt in following:
				if nxt.type == "Section Break":
					break
				if nxt.type == "Link" and nxt.child:
					has_child = True
					break
			if not has_child:
				continue
		keep.append(item)

	sidebar.set("items", [])
	for item in keep:
		sidebar.append("items", item.as_dict(no_default_fields=True))


def _sync_desktop_icon() -> None:
	"""Own the Desktop Icon so it nests under Frappe HR and keeps our artwork.

	Two fields matter:

	* `parent_icon` - the tile is only shown *inside* the Frappe HR folder when
	  this points at that app's icon; left empty it floats on the desktop root.
	* `app` - Frappe resolves the tile image from
	  `assets/<app>/icons/desktop_icons/<style>/<scrub(label)>.svg`. The workspace
	  is mounted on "hrms", so the auto-generated row would look inside hrms and
	  find nothing; shipping the SVG there would mean editing another app.
	  Pinning `app` to "ai_hr" keeps the lookup on our own asset.

	`create_desktop_icons` only creates rows that don't already exist, so this
	survives regeneration.
	"""
	if not frappe.db.exists("DocType", "Desktop Icon"):
		return

	# The Frappe HR folder tile; without it there is nothing to nest under.
	parent = frappe.db.get_value(
		"Desktop Icon", {"label": "Frappe HR", "icon_type": "App"}, "name"
	) or frappe.db.get_value("Desktop Icon", {"label": "Frappe HR"}, "name")

	values = {
		"app": "ai_hr",
		"icon": "sparkles",
		"link_type": "Workspace Sidebar",
		"link_to": WORKSPACE,
	}
	if parent:
		values["parent_icon"] = parent

	existing = frappe.db.get_value("Desktop Icon", {"label": WORKSPACE}, "name")
	if existing:
		frappe.db.set_value("Desktop Icon", existing, values, update_modified=False)
		return

	try:
		frappe.get_doc(
			{"doctype": "Desktop Icon", "label": WORKSPACE, "icon_type": "Link", **values}
		).insert(ignore_permissions=True)
	except Exception:
		# A desktop tile is cosmetic - never let it block the mount.
		frappe.log_error(title="AI HR: could not create desktop icon", message=frappe.get_traceback())


# -- public job application form ----------------------------------------------

WEB_FORM = "job-application"
FORM_CSS = "public/css/job_application.css"

#: Marker so the block can be identified and replaced without duplicating.
CSS_MARKER = "/* ai_hr:job-application */"


def style_job_application_form() -> None:
	"""Apply this app's stylesheet to the public Job Application web form.

	The form is a *standard* web form owned by hrms, so its record is re-synced
	from hrms's JSON on every migrate - which blanks `custom_css`. Re-applying it
	from `after_migrate` (this runs after that sync) keeps the styling without
	editing hrms source.

	The `webform_include_css` hook cannot be used here: Frappe only reads it when
	a <web_form_name>.css already exists beside the web form module, and hrms
	ships none.
	"""
	if not frappe.db.exists("Web Form", WEB_FORM):
		return

	import os

	css_path = os.path.join(frappe.get_app_path("ai_hr"), *FORM_CSS.split("/"))
	if not os.path.exists(css_path):
		return

	with open(css_path) as handle:
		css = handle.read()

	block = f"{CSS_MARKER}\n{css}"
	current = frappe.db.get_value("Web Form", WEB_FORM, "custom_css") or ""

	# Idempotent: skip when unchanged, replace wholesale when it is.
	if current.strip() == block.strip():
		return

	frappe.db.set_value("Web Form", WEB_FORM, "custom_css", block, update_modified=False)
	frappe.clear_cache()


# -- website footer -----------------------------------------------------------

FOOTER_TEMPLATE = "Starrich Footer"


def use_starrich_footer() -> None:
	"""Point the website at this app's footer instead of Frappe's default.

	`Website Settings.footer_template` is the supported way to swap the site
	footer, so no core template is shadowed. Without this the page renders
	"Standard Footer", which erpnext extends with its "Powered by ERPNext" line.

	Idempotent, and it never overrides a footer the admin picked themselves -
	only an empty setting or the stock default is replaced.
	"""
	if not frappe.db.exists("Web Template", FOOTER_TEMPLATE):
		return  # not synced yet (first migrate installs it)

	current = frappe.db.get_single_value("Website Settings", "footer_template")
	if current not in (None, "", "Standard Footer"):
		return

	frappe.db.set_single_value("Website Settings", "footer_template", FOOTER_TEMPLATE)
	frappe.clear_cache()


# -- brand assets -------------------------------------------------------------

LOGO = "/assets/ai_hr/images/starrich-logo.png"
#: The star alone. The full lockup is ~3.5:1 and unreadable at 32px.
ICON = "/assets/ai_hr/images/starrich-icon.png"
BRAND_NAME = "Starrich HR"

#: Values this app is allowed to replace. Anything else is treated as a
#: deliberate choice by the administrator and left alone. `starrich-logo.svg`
#: is the placeholder an earlier version of this app shipped; it no longer
#: exists on disk, so any field still pointing at it is a broken image.
_REPLACEABLE = {
	None,
	"",
	"/assets/ai_hr/images/starrich-logo.svg",
	"/assets/frappe/images/frappe-framework-logo.svg",
	"/assets/frappe/images/frappe-favicon.svg",
}

#: (doctype, fieldname, value). The hooks in hooks.py cover the Desk, but the
#: website navbar, tab icon and boot splash read these stored settings - which
#: is why changing only the hook left the old logo on screen.
BRAND_FIELDS = [
	("Website Settings", "app_logo", LOGO),
	("Website Settings", "banner_image", LOGO),
	("Website Settings", "splash_image", LOGO),
	("Website Settings", "favicon", ICON),
	("Navbar Settings", "app_logo", LOGO),
]


def apply_brand_assets() -> None:
	"""Point the stored brand settings at this app's artwork.

	Idempotent, and deliberately conservative: a value the administrator set
	themselves is never overwritten - only an empty field, a Frappe default, or
	the retired placeholder.
	"""
	changed = []

	for doctype, field, value in BRAND_FIELDS:
		if not frappe.db.exists("DocType", doctype):
			continue
		meta = frappe.get_meta(doctype)
		if not meta.has_field(field):
			continue

		current = frappe.db.get_single_value(doctype, field)
		if current == value:
			continue
		if current not in _REPLACEABLE:
			continue  # someone chose this on purpose

		frappe.db.set_single_value(doctype, field, value)
		changed.append(f"{doctype}.{field}")

	# The stock name reads "Frappe" in the browser title, the Desk and the
	# website copyright line.
	for doctype in ("Website Settings", "System Settings"):
		current = frappe.db.get_single_value(doctype, "app_name")
		if current in (None, "", "Frappe", "Frappe HR"):
			frappe.db.set_single_value(doctype, "app_name", BRAND_NAME)
			changed.append(f"{doctype}.app_name")

	if changed:
		frappe.clear_cache()


# -- dashboards ---------------------------------------------------------------
#
# Four HR workspaces ship with no charts or number cards at all (AI HR, HR Setup,
# Tax & Benefits, Tenure), so their dashboards are link lists with nothing to
# look at. These add one or two widgets each.
#
# A workspace renders a chart only when three things line up: the Dashboard Chart
# record exists, the workspace has a row in its `charts` table, and its `content`
# JSON carries a matching block. All three are handled below.
#
# The hrms-owned workspaces are re-synced from their JSON on every migrate, which
# drops these additions - hence re-applying from after_migrate rather than
# editing hrms source.

#: (chart name, workspace, doctype, group-by field, aggregate, value field, chart style, filters)
DASHBOARD_CHARTS = [
	("AI Match Verdicts", "AI HR", "AI Candidate Score", "verdict",
	 "Count", None, "Donut", [["AI Candidate Score", "scoring_status", "=", "Completed"]]),
	("CV Parsing Status", "AI HR", "AI Resume Analysis", "parsing_status",
	 "Count", None, "Donut", []),
	("Headcount by Department", "Tenure", "Employee", "department",
	 "Count", None, "Bar", [["Employee", "status", "=", "Active"]]),
	("Grievances by Status", "Tenure", "Employee Grievance", "status",
	 "Count", None, "Donut", []),
	("Employees by Grade", "HR Setup", "Employee", "grade",
	 "Count", None, "Bar", [["Employee", "status", "=", "Active"]]),
	("Tax Exemptions by Employee", "Tax & Benefits", "Employee Tax Exemption Declaration",
	 "employee", "Sum", "total_exemption_amount", "Bar", []),
]

#: (card label, workspace, doctype, function, value field, filters)
DASHBOARD_CARDS = [
	("Candidates Scored", "AI HR", "AI Candidate Score", "Count", None,
	 [["AI Candidate Score", "scoring_status", "=", "Completed"]]),
	("Active Employees", "Tenure", "Employee", "Count", None,
	 [["Employee", "status", "=", "Active"]]),
	("Open Grievances", "Tenure", "Employee Grievance", "Count", None,
	 [["Employee Grievance", "status", "=", "Open"]]),
	("Total Declared Exemptions", "Tax & Benefits", "Employee Tax Exemption Declaration",
	 "Sum", "total_exemption_amount", []),
]


def install_dashboards() -> None:
	"""Create the charts/cards and attach them to their workspaces."""
	import json

	created = []

	for name, ws, doctype, group_field, agg, value_field, style, filters in DASHBOARD_CHARTS:
		if not frappe.db.exists("DocType", doctype):
			continue
		if not frappe.get_meta(doctype).has_field(group_field):
			continue
		if not frappe.db.exists("Dashboard Chart", name):
			chart = frappe.get_doc({
				"doctype": "Dashboard Chart",
				"__newname": name,
				"chart_name": name,
				"chart_type": "Group By",
				"document_type": doctype,
				"group_by_type": agg,
				"group_by_based_on": group_field,
				"aggregate_function_based_on": value_field,
				"number_of_groups": 8,
				"type": style,
				"filters_json": json.dumps(filters),
				"timeseries": 0,
				"is_public": 1,
				"owner": "Administrator",
			})
			try:
				chart.insert(ignore_permissions=True)
				created.append(name)
			except Exception:
				frappe.log_error(title=f"AI HR: could not create chart {name}",
				                 message=frappe.get_traceback())
				continue
		_attach_to_workspace(ws, "chart", name)

	for label, ws, doctype, func, value_field, filters in DASHBOARD_CARDS:
		if not frappe.db.exists("DocType", doctype):
			continue
		if not frappe.db.exists("Number Card", label):
			card = frappe.get_doc({
				"doctype": "Number Card",
				"__newname": label,
				"label": label,
				"type": "Document Type",
				"document_type": doctype,
				"function": func,
				"aggregate_function_based_on": value_field,
				"filters_json": json.dumps(filters),
				"is_public": 1,
				"show_percentage_stats": 0,
				"owner": "Administrator",
			})
			try:
				card.insert(ignore_permissions=True)
				created.append(label)
			except Exception:
				frappe.log_error(title=f"AI HR: could not create number card {label}",
				                 message=frappe.get_traceback())
				continue
		_attach_to_workspace(ws, "card", label)

	frappe.db.commit()
	return created


def _attach_to_workspace(workspace: str, kind: str, name: str) -> None:
	"""Add a chart/card to a workspace's layout.

	Two paths, because v17 refuses direct edits to app-shipped workspaces
	("Standard workspaces can't be edited directly"):

	* **Standard** (Tenure, HR Setup, Tax & Benefits - owned by hrms) go through
	  `upsert_content_customization`, the sanctioned delta. Frappe's own comment
	  notes these survive app updates, so there is no need to re-apply on migrate.
	* **Non-standard** (this app's own AI HR workspace) are edited directly.
	"""
	import json

	if not frappe.db.exists("Workspace", workspace):
		return

	block_type = "chart" if kind == "chart" else "number_card"
	key = f"{block_type}_name"

	ws = frappe.get_doc("Workspace", workspace)

	# Read the *current* layout, which for a standard workspace lives on the
	# customization once one exists. Reading the base every time made each call
	# overwrite the previous one, so only the last widget survived.
	from frappe.desk.doctype.workspace_customization.workspace_customization import (
		get_customization,
	)

	customization = get_customization(workspace) if ws.standard else None
	base_content = (customization.content if customization and customization.content
	                else ws.content)
	content = json.loads(base_content or "[]")

	# Already laid out? Nothing to do.
	if any(b.get("type") == block_type and (b.get("data") or {}).get(key) == name
	       for b in content):
		return

	block = {
		"id": f"aihr{abs(hash(name)) % 10**8}",
		"type": block_type,
		"data": {key: name, "col": 6 if kind == "chart" else 4},
	}
	content.insert(0, block)   # widgets first, above the existing link cards

	if ws.standard:
		from frappe.desk.doctype.workspace_customization.workspace_customization import (
			upsert_content_customization,
		)

		# `new_widgets` carries the item definitions for blocks the site added, so
		# they can be resolved at render time (the base child tables are untouched).
		widget_row = {"chart_name": name, "label": name} if kind == "chart" \
			else {"number_card_name": name, "label": name}
		upsert_content_customization(workspace, content, {block_type: [widget_row]})
		return

	if kind == "chart":
		if not any(c.chart_name == name for c in (ws.charts or [])):
			ws.append("charts", {"chart_name": name, "label": name})
	else:
		if not any(c.number_card_name == name for c in (ws.number_cards or [])):
			ws.append("number_cards", {"number_card_name": name, "label": name})

	ws.content = json.dumps(content)
	ws.flags.ignore_links = True
	ws.save(ignore_permissions=True)


# -- chart readability --------------------------------------------------------
#
# Long category names used to collide in pie/donut legends. The cause is
# frappe/public/js/frappe/widgets/chart_widget.js, which builds its options with
# `truncateLegends: 0` - every other chart surface in Frappe (report view, form
# dashboard, report utils) passes 1, and the charting library's own default is 1.
#
# The fix is in ai_hr_desktop.bundle.js, which re-enables truncation on the
# widget class at runtime. Chart *types* are deliberately left alone: pie stays
# pie.


# -- region-specific reports --------------------------------------------------

#: Payroll reports that only work on an India-configured site.
#:
#: hrms ships these in the Payroll module with no region guard, so they appear on
#: every site. "Professional Tax Deductions" reads `Salary Component.component_type`,
#: a custom field created only by hrms/regional/india/setup.py, so on a non-India
#: site opening it raises:
#:
#:     Unknown column 'component_type' in 'SELECT'
#:
#: Professional Tax is an Indian state tax with no Tanzanian equivalent, so the
#: report is disabled rather than propped up by creating India payroll fields on
#: a Tanzanian company.
#: Emptied deliberately: "Professional Tax Deductions" is now supported by
#: creating the `component_type` field it reads (see
#: ai_hr.demo_hr.seed_professional_tax) rather than hiding the report.
INDIA_ONLY_REPORTS: list[str] = []


def disable_inapplicable_reports() -> None:
	"""Disable region-specific reports that cannot run on this site.

	Idempotent, and re-enables them automatically if the company is ever moved to
	India - so this is a guard, not a permanent removal.
	"""
	country = frappe.db.get_value("Company", {"name": frappe.defaults.get_global_default("company")},
	                              "country") or frappe.db.get_value("Company", {}, "country")
	india = (country or "").strip().lower() == "india"

	# Iterating only the current list would strand a report that was disabled by
	# an earlier version and has since been removed from it, so every report this
	# function has ever managed is reconciled here.
	MANAGED = set(INDIA_ONLY_REPORTS) | {"Professional Tax Deductions"}
	for name in MANAGED:
		if not frappe.db.exists("Report", name):
			continue
		should_disable = 1 if (name in INDIA_ONLY_REPORTS and not india) else 0
		if frappe.db.get_value("Report", name, "disabled") != should_disable:
			frappe.db.set_value("Report", name, "disabled", should_disable, update_modified=False)

	frappe.db.commit()


# -- HR read access to payroll masters ----------------------------------------

#: Doctypes an HR user must be able to *read* for payroll and expense screens to
#: work, but which ship with read access only for Sales / Purchase / Accounts /
#: System Manager roles.
#:
#: Without these a pure HR user opening Salary Register is stopped with
#: "You do not have permission to access Currency: TZS." The gap is easy to miss
#: because an administrator also holds System Manager and never sees it.
#:
#: Read only - nothing here grants write, create, delete or submit.
HR_READ_DOCTYPES = [
	"Currency",
	"Account",
	"Cost Center",
	"Fiscal Year",
	"Mode of Payment",
	"Bank",
	"Bank Account",
	"Item",
	"Customer",
	"Project",
]

HR_ROLES = ["HR Manager", "HR User"]


def grant_hr_read_access() -> None:
	"""Give HR roles read-only access to the masters payroll screens depend on.

	Uses Custom DocPerm so the shipped DocPerms stay untouched and an app update
	cannot silently revert it. Idempotent.
	"""
	from frappe.permissions import add_permission, update_permission_property

	granted = []
	for doctype in HR_READ_DOCTYPES:
		if not frappe.db.exists("DocType", doctype):
			continue
		for role in HR_ROLES:
			if frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": role,
			                                       "permlevel": 0}):
				continue
			try:
				add_permission(doctype, role, 0)
				# add_permission grants read by default; make the intent explicit
				# and ensure nothing else was switched on.
				for ptype in ("write", "create", "delete", "submit", "cancel", "amend"):
					update_permission_property(doctype, role, 0, ptype, 0)
				update_permission_property(doctype, role, 0, "read", 1)
				granted.append(f"{doctype}/{role}")
			except Exception:
				frappe.log_error(title=f"AI HR: could not grant {role} read on {doctype}",
				                 message=frappe.get_traceback())

	if granted:
		frappe.clear_cache()
		frappe.db.commit()
	return granted


# -- navbar clean-up ----------------------------------------------------------

#: Navbar dropdown entries hidden on this white-labelled system.
#:
#: "About" opens a dialog showing the Frappe wordmark, Frappe's website and
#: GitHub links, and the Frappe copyright line. There is no supported way to
#: restyle that dialog, so the entry that opens it is hidden instead.
#: (App versions remain available from the bench: `bench version`.)
HIDDEN_NAVBAR_ITEMS = ["About"]

#: Navbar entries rebranded rather than hidden.
#:
#: The desk avatar menu already re-points "Frappe Support" at our own help desk;
#: this does the same for the sidebar help menu, which is a separate surface.
#:
#: Each entry lists every label the row may currently carry -- the stock one and
#: the one we rename it to -- so a second run still matches the row it already
#: renamed instead of silently doing nothing.
RELABELLED_NAVBAR_ITEMS = [
	(("Frappe Support", "Starrich Support"), "Starrich Support", "/app/issue/new"),
]


def hide_navbar_items() -> None:
	"""Hide/rebrand the Frappe-branded entries in the navbar dropdowns. Idempotent."""
	if not frappe.db.exists("DocType", "Navbar Settings"):
		return

	settings = frappe.get_single("Navbar Settings")
	changed = False

	for field in ("help_dropdown", "settings_dropdown"):
		for item in settings.get(field) or []:
			if item.item_label in HIDDEN_NAVBAR_ITEMS and not item.hidden:
				item.hidden = 1
				changed = True
				continue

			for labels, new_label, route in RELABELLED_NAVBAR_ITEMS:
				if item.item_label not in labels:
					continue
				# `hidden` is cleared too: an earlier revision hid this row before
				# we settled on rebranding it, and those sites still carry the flag.
				wanted = (new_label, "Route", route, 0)
				if (item.item_label, item.item_type, item.route, item.hidden) != wanted:
					item.item_label, item.item_type, item.route, item.hidden = wanted
					changed = True
				break

	if changed:
		settings.save(ignore_permissions=True)
		frappe.clear_cache()
		frappe.db.commit()
