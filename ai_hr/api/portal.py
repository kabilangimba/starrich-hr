"""Summary tiles for the Starrich HR landing screen (the /app/desktop apps page).

Everything here is read-only and permission-checked. Each tile is computed
independently and a tile the user cannot see is simply omitted, so a recruiter
without Payroll access gets a shorter page rather than an error.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import add_days, getdate, nowdate


@frappe.whitelist()
def get_summary() -> dict[str, Any]:
	"""Return the landing-screen tiles the current user is allowed to see."""
	return {
		"greeting": _greeting(),
		"user": frappe.utils.get_fullname(frappe.session.user),
		"tiles": [t for t in (_recruitment(), _people(), _leave(), _interviews()) if t],
	}


def _greeting() -> str:
	"""Time-of-day greeting in the user's own timezone."""
	hour = frappe.utils.now_datetime().hour
	if hour < 12:
		return _("Good morning")
	if hour < 17:
		return _("Good afternoon")
	return _("Good evening")


def _count(doctype: str, filters: dict | None = None) -> int:
	"""Permission-safe count. Returns 0 when the doctype is absent or blocked."""
	if not frappe.db.exists("DocType", doctype):
		return 0
	if not frappe.has_permission(doctype, "read"):
		return 0
	try:
		return frappe.db.count(doctype, filters or {})
	except Exception:
		# A tile is decoration - never let a bad filter break the landing page.
		return 0


def _recruitment() -> dict | None:
	if not frappe.has_permission("Job Applicant", "read"):
		return None

	open_roles = _count("Job Opening", {"status": "Open"})
	# `ats_stage` is this app's field; fall back to stock status if absent.
	if frappe.db.has_column("Job Applicant", "ats_stage"):
		in_review = _count("Job Applicant", {"ats_stage": ["in", ["Applied", "CV Screening", "AI Screening"]]})
	else:
		in_review = _count("Job Applicant", {"status": "Open"})

	return {
		"key": "recruitment",
		"icon": "briefcase",
		"label": _("Recruitment"),
		"value": in_review,
		"unit": _("candidates in review"),
		"hint": _("{0} open role(s)").format(open_roles),
		"route": "/desk/job-applicant",
	}


def _people() -> dict | None:
	if not frappe.has_permission("Employee", "read"):
		return None

	active = _count("Employee", {"status": "Active"})
	# Joined in the last 30 days - the number an HR lead actually watches.
	recent = _count("Employee", {"date_of_joining": [">=", add_days(nowdate(), -30)], "status": "Active"})

	return {
		"key": "people",
		"icon": "users",
		"label": _("People"),
		"value": active,
		"unit": _("active employees"),
		"hint": _("{0} joined in the last 30 days").format(recent),
		"route": "/desk/employee",
	}


def _leave() -> dict | None:
	if not frappe.has_permission("Leave Application", "read"):
		return None

	pending = _count("Leave Application", {"status": "Open"})
	today = getdate(nowdate())
	on_leave = _count(
		"Leave Application",
		{"status": "Approved", "from_date": ["<=", today], "to_date": [">=", today]},
	)

	return {
		"key": "leave",
		"icon": "calendar-days",
		"label": _("Time Off"),
		"value": pending,
		"unit": _("pending approvals"),
		"hint": _("{0} away today").format(on_leave),
		"route": "/desk/leave-application",
	}


def _interviews() -> dict | None:
	if not frappe.db.exists("DocType", "AI Interview"):
		return None
	if not frappe.has_permission("AI Interview", "read"):
		return None

	scheduled = _count("AI Interview", {"status": ["!=", "Completed"]})
	scored = _count("AI Candidate Score", {"scoring_status": "Completed"})

	return {
		"key": "interviews",
		"icon": "sparkles",
		"label": _("AI Screening"),
		"value": scored,
		"unit": _("candidates scored"),
		"hint": _("{0} interview(s) open").format(scheduled),
		"route": "/desk/ai-hr",
	}
