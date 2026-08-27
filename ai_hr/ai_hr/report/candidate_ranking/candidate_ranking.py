"""Candidate Ranking report (proposal §5).

Ranks scored applicants for an opening. Sorting, filtering and search come from
Frappe's report view, so this only has to return correct, permission-safe rows.
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
		{"fieldname": "rank", "label": _("Rank"), "fieldtype": "Int", "width": 60},
		{
			"fieldname": "job_applicant",
			"label": _("Candidate"),
			"fieldtype": "Link",
			"options": "Job Applicant",
			"width": 180,
		},
		{"fieldname": "applicant_name", "label": _("Name"), "fieldtype": "Data", "width": 160},
		{
			"fieldname": "overall_score",
			"label": _("Overall"),
			"fieldtype": "Percent",
			"width": 90,
		},
		{"fieldname": "verdict", "label": _("Verdict"), "fieldtype": "Data", "width": 120},
		{"fieldname": "skills_score", "label": _("Skills"), "fieldtype": "Percent", "width": 80},
		{
			"fieldname": "experience_score",
			"label": _("Experience"),
			"fieldtype": "Percent",
			"width": 90,
		},
		{"fieldname": "education_score", "label": _("Education"), "fieldtype": "Percent", "width": 90},
		{"fieldname": "ats_stage", "label": _("ATS Stage"), "fieldtype": "Data", "width": 130},
		{
			"fieldname": "total_years_experience",
			"label": _("Years Exp"),
			"fieldtype": "Float",
			"width": 90,
		},
		{"fieldname": "location", "label": _("Location"), "fieldtype": "Data", "width": 140},
		{"fieldname": "missing_requirements", "label": _("Gaps"), "fieldtype": "Small Text", "width": 220},
		{
			"fieldname": "score_doc",
			"label": _("Score"),
			"fieldtype": "Link",
			"options": "AI Candidate Score",
			"width": 110,
		},
	]


def get_data(filters: dict[str, Any]) -> list[dict[str, Any]]:
	conditions: dict[str, Any] = {"scoring_status": "Completed"}
	if filters.get("job_opening"):
		conditions["job_opening"] = filters["job_opening"]
	if filters.get("verdict"):
		conditions["verdict"] = filters["verdict"]
	if filters.get("minimum_score"):
		conditions["overall_score"] = [">=", filters["minimum_score"]]

	scores = frappe.get_all(
		"AI Candidate Score",
		filters=conditions,
		fields=[
			"name as score_doc",
			"job_applicant",
			"overall_score",
			"verdict",
			"skills_score",
			"experience_score",
			"education_score",
			"missing_requirements",
		],
		order_by="overall_score desc",
		# Respect the reading user's permissions rather than returning every row.
		ignore_permissions=False,
	)
	if not scores:
		return []

	applicants = {a: None for a in {s["job_applicant"] for s in scores}}
	for row in frappe.get_all(
		"Job Applicant",
		filters={"name": ["in", list(applicants)]},
		fields=["name", "applicant_name", "ats_stage"],
	):
		applicants[row["name"]] = row

	# Profile detail lives on the analysis, one query rather than one per row.
	analyses: dict[str, dict] = {}
	for row in frappe.get_all(
		"AI Resume Analysis",
		filters={"job_applicant": ["in", list(applicants)], "parsing_status": "Completed"},
		fields=["job_applicant", "total_years_experience", "location"],
	):
		analyses[row["job_applicant"]] = row

	data = []
	for index, score in enumerate(scores, start=1):
		applicant = applicants.get(score["job_applicant"]) or {}
		analysis = analyses.get(score["job_applicant"]) or {}
		data.append(
			{
				**score,
				"rank": index,
				"applicant_name": applicant.get("applicant_name"),
				"ats_stage": applicant.get("ats_stage"),
				"total_years_experience": analysis.get("total_years_experience"),
				"location": analysis.get("location"),
			}
		)
	return data
