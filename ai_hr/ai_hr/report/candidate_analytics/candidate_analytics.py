"""Candidate Analytics.

Pipeline shape: how many candidates sit at each ATS stage, and how well they
score. Aggregated from records already in the system - no AI call.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from ai_hr.setup import ATS_STAGES


def execute(filters: dict[str, Any] | None = None) -> tuple[list[dict], list[dict]]:
	filters = filters or {}
	return get_columns(), get_data(filters)


def get_columns() -> list[dict[str, Any]]:
	return [
		{"fieldname": "stage", "label": _("ATS Stage"), "fieldtype": "Data", "width": 170},
		{"fieldname": "candidates", "label": _("Candidates"), "fieldtype": "Int", "width": 110},
		{"fieldname": "share", "label": _("Share of Pipeline"), "fieldtype": "Percent", "width": 140},
		{"fieldname": "scored", "label": _("AI Scored"), "fieldtype": "Int", "width": 100},
		{"fieldname": "avg_score", "label": _("Avg Score"), "fieldtype": "Percent", "width": 110},
		{"fieldname": "best_score", "label": _("Best Score"), "fieldtype": "Percent", "width": 110},
	]


def get_data(filters: dict[str, Any]) -> list[dict[str, Any]]:
	if not frappe.has_permission("Job Applicant", "read"):
		frappe.throw(_("You do not have permission to read candidate data."), frappe.PermissionError)

	applicant_filters: dict[str, Any] = {}
	if filters.get("job_opening"):
		applicant_filters["job_title"] = filters["job_opening"]

	has_stage = frappe.db.has_column("Job Applicant", "ats_stage")
	fields = ["name", "status"] + (["ats_stage"] if has_stage else [])
	applicants = frappe.get_all(
		"Job Applicant", filters=applicant_filters, fields=fields, limit_page_length=0
	)
	if not applicants:
		return []

	# One query for every score, then group in Python - cheaper than a query per stage.
	scores = {
		s.job_applicant: s.overall_score
		for s in frappe.get_all(
			"AI Candidate Score",
			filters={"scoring_status": "Completed"},
			fields=["job_applicant", "overall_score"],
			limit_page_length=0,
		)
	}

	buckets: dict[str, list] = {}
	for a in applicants:
		stage = (a.get("ats_stage") if has_stage else None) or a.get("status") or _("Unknown")
		buckets.setdefault(stage, []).append(a.name)

	total = len(applicants)
	rows = []
	for stage, names in buckets.items():
		vals = [scores[n] for n in names if scores.get(n) is not None]
		rows.append(
			{
				"stage": stage,
				"candidates": len(names),
				"share": round(len(names) * 100.0 / total, 1),
				"scored": len(vals),
				"avg_score": round(sum(vals) / len(vals), 1) if vals else 0,
				"best_score": round(max(vals), 1) if vals else 0,
			}
		)

	# Present in pipeline order where possible, unknown stages last.
	order = {name: i for i, name in enumerate(ATS_STAGES)}
	rows.sort(key=lambda r: order.get(r["stage"], len(order)))
	return rows
