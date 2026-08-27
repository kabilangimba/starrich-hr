"""AI Skill Gap Analysis.

Compares the skills a candidate actually has (from their parsed CV) against the
skills an opening requires, and reports what is missing.

Everything here is derived from records this app already produces - it makes no
AI call of its own, so it is fast, free to run and works with no provider
configured. The advisory rule still applies: a gap is information for the
recruiter, never a rejection (proposal §15).
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _


def execute(filters: dict[str, Any] | None = None) -> tuple[list[dict], list[dict]]:
	filters = filters or {}
	return get_columns(), get_data(filters)


def get_columns() -> list[dict[str, Any]]:
	return [
		{
			"fieldname": "job_applicant",
			"label": _("Candidate"),
			"fieldtype": "Link",
			"options": "Job Applicant",
			"width": 170,
		},
		{"fieldname": "applicant_name", "label": _("Name"), "fieldtype": "Data", "width": 150},
		{
			"fieldname": "job_opening",
			"label": _("Opening"),
			"fieldtype": "Link",
			"options": "Job Opening",
			"width": 160,
		},
		{"fieldname": "coverage", "label": _("Skill Coverage"), "fieldtype": "Percent", "width": 110},
		{"fieldname": "matched_count", "label": _("Matched"), "fieldtype": "Int", "width": 80},
		{"fieldname": "missing_count", "label": _("Missing"), "fieldtype": "Int", "width": 80},
		{"fieldname": "missing_skills", "label": _("Missing Skills"), "fieldtype": "Data", "width": 260},
		{"fieldname": "matched_skills", "label": _("Matched Skills"), "fieldtype": "Data", "width": 240},
		{
			"fieldname": "recommendation",
			"label": _("Suggested Training"),
			"fieldtype": "Data",
			"width": 240,
		},
	]


def get_data(filters: dict[str, Any]) -> list[dict[str, Any]]:
	if not frappe.has_permission("Job Applicant", "read"):
		frappe.throw(_("You do not have permission to read candidate data."), frappe.PermissionError)

	opening = filters.get("job_opening")
	score_filters: dict[str, Any] = {"scoring_status": "Completed"}
	if opening:
		score_filters["job_opening"] = opening

	scores = frappe.get_all(
		"AI Candidate Score",
		filters=score_filters,
		fields=["job_applicant", "job_opening", "overall_score"],
		order_by="overall_score desc",
		limit_page_length=500,
	)

	# Required skills are per-opening, so resolve each one once rather than per row.
	required_cache: dict[str, list[str]] = {}
	rows: list[dict[str, Any]] = []

	for score in scores:
		required = required_cache.setdefault(
			score.job_opening, _required_skills(score.job_opening)
		)
		if not required:
			# Nothing declared on the opening means there is no gap to measure;
			# showing 100% here would be a false positive.
			continue

		owned = _candidate_skills(score.job_applicant)
		owned_lower = [s.lower() for s in owned]

		matched, missing = [], []
		for skill in required:
			# Substring both ways so "AWS" matches "AWS Lambda" and vice versa.
			needle = skill.lower()
			if any(needle in have or have in needle for have in owned_lower):
				matched.append(skill)
			else:
				missing.append(skill)

		applicant_name = frappe.db.get_value("Job Applicant", score.job_applicant, "applicant_name")

		rows.append(
			{
				"job_applicant": score.job_applicant,
				"applicant_name": applicant_name,
				"job_opening": score.job_opening,
				"coverage": round(len(matched) * 100.0 / len(required), 1),
				"matched_count": len(matched),
				"missing_count": len(missing),
				"missing_skills": ", ".join(missing),
				"matched_skills": ", ".join(matched),
				"recommendation": _recommend(missing),
			}
		)

	rows.sort(key=lambda r: r["coverage"], reverse=True)
	return rows


def _required_skills(job_opening: str) -> list[str]:
	"""Skills declared on the opening, via this app's `ai_required_skills` table."""
	if not job_opening or not frappe.db.exists("Job Opening", job_opening):
		return []
	try:
		doc = frappe.get_doc("Job Opening", job_opening)
	except frappe.PermissionError:
		return []

	skills = []
	for row in doc.get("ai_required_skills") or []:
		name = (row.get("skill_name") or "").strip()
		if name:
			skills.append(name)
	return skills


def _candidate_skills(job_applicant: str) -> list[str]:
	"""Skills extracted from the candidate's most recent completed CV parse."""
	analysis = frappe.db.get_value(
		"AI Resume Analysis",
		{"job_applicant": job_applicant, "parsing_status": "Completed"},
		"name",
	)
	if not analysis:
		return []

	return frappe.get_all(
		"AI Resume Skill",
		filters={"parent": analysis, "parenttype": "AI Resume Analysis"},
		pluck="skill_name",
	)


def _recommend(missing: list[str]) -> str:
	"""A plain-language training hint. Deliberately not an AI call."""
	if not missing:
		return _("No gap - candidate covers the declared requirements")
	if len(missing) <= 2:
		return _("Short course or on-the-job coaching in {0}").format(", ".join(missing))
	return _("Structured training needed across {0} areas, starting with {1}").format(
		len(missing), ", ".join(missing[:2])
	)
