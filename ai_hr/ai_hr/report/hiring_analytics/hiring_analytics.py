"""Hiring Analytics.

One row per job opening: how many applied, how far they got, and how the AI
scored them. Aggregated from existing records - no AI call.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import date_diff, nowdate


def execute(filters: dict[str, Any] | None = None) -> tuple[list[dict], list[dict]]:
	filters = filters or {}
	return get_columns(), get_data(filters)


def get_columns() -> list[dict[str, Any]]:
	return [
		{
			"fieldname": "job_opening",
			"label": _("Opening"),
			"fieldtype": "Link",
			"options": "Job Opening",
			"width": 190,
		},
		{"fieldname": "job_title", "label": _("Title"), "fieldtype": "Data", "width": 160},
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 90},
		{"fieldname": "days_open", "label": _("Days Open"), "fieldtype": "Int", "width": 100},
		{"fieldname": "applicants", "label": _("Applicants"), "fieldtype": "Int", "width": 100},
		{"fieldname": "scored", "label": _("AI Scored"), "fieldtype": "Int", "width": 100},
		{"fieldname": "shortlisted", "label": _("Shortlisted"), "fieldtype": "Int", "width": 110},
		{"fieldname": "hired", "label": _("Hired"), "fieldtype": "Int", "width": 80},
		{"fieldname": "avg_score", "label": _("Avg Score"), "fieldtype": "Percent", "width": 110},
	]


def get_data(filters: dict[str, Any]) -> list[dict[str, Any]]:
	if not frappe.has_permission("Job Opening", "read"):
		frappe.throw(_("You do not have permission to read job openings."), frappe.PermissionError)

	opening_filters: dict[str, Any] = {}
	if filters.get("status"):
		opening_filters["status"] = filters["status"]

	openings = frappe.get_all(
		"Job Opening",
		filters=opening_filters,
		# `posted_on` is when the role went live; `creation` is only when the row was
		# inserted, which for imported or seeded data is not the same thing.
		fields=["name", "job_title", "status", "posted_on", "closed_on", "creation"],
		limit_page_length=0,
	)
	if not openings:
		return []

	has_stage = frappe.db.has_column("Job Applicant", "ats_stage")
	fields = ["name", "job_title", "status"] + (["ats_stage"] if has_stage else [])
	applicants = frappe.get_all("Job Applicant", fields=fields, limit_page_length=0)

	scores = {
		s.job_applicant: s.overall_score
		for s in frappe.get_all(
			"AI Candidate Score",
			filters={"scoring_status": "Completed"},
			fields=["job_applicant", "overall_score"],
			limit_page_length=0,
		)
	}

	by_opening: dict[str, list] = {}
	for a in applicants:
		# Job Applicant.job_title is a Link to Job Opening in HRMS.
		by_opening.setdefault(a.job_title, []).append(a)

	today = nowdate()
	rows = []
	for o in openings:
		mine = by_opening.get(o.name, [])
		vals = [scores[a.name] for a in mine if scores.get(a.name) is not None]

		def stage_of(a):
			return (a.get("ats_stage") if has_stage else None) or a.get("status") or ""

		# Closed roles stop accruing days; open ones count to today.
		opened = o.posted_on or o.creation
		until = o.closed_on or today

		rows.append(
			{
				"job_opening": o.name,
				"job_title": o.job_title,
				"status": o.status,
				"days_open": max(date_diff(until, opened), 0),
				"applicants": len(mine),
				"scored": len(vals),
				"shortlisted": sum(
					1
					for a in mine
					if stage_of(a) in ("Shortlisted", "Phone Interview", "Technical Interview", "Final Interview", "Offer")
				),
				"hired": sum(1 for a in mine if stage_of(a) in ("Hired", "Accepted")),
				"avg_score": round(sum(vals) / len(vals), 1) if vals else 0,
			}
		)

	rows.sort(key=lambda r: r["applicants"], reverse=True)
	return rows
