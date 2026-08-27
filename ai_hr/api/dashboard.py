"""ATS dashboard metrics (proposal §10).

One round trip returns everything the dashboard renders. All queries run through
the ORM under the calling user's permissions.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.query_builder.functions import Count
from frappe.utils import add_days, getdate, nowdate

from ai_hr.setup import ATS_STAGES

#: Ordered funnel stages. Withdrawn/Rejected/On Hold are exits, not steps, so
#: they are reported separately rather than as part of the funnel.
FUNNEL_STAGES = [
	"Applied",
	"CV Screening",
	"AI Screening",
	"Shortlisted",
	"Phone Interview",
	"Technical Interview",
	"Final Interview",
	"Offer",
	"Hired",
]

EXIT_STAGES = ["Rejected", "Withdrawn", "On Hold"]

SCORE_BANDS = [
	("90-100", 90, 101),
	("75-89", 75, 90),
	("60-74", 60, 75),
	("0-59", 0, 60),
]


@frappe.whitelist()
def get_metrics(days: int = 30) -> dict[str, Any]:
	"""Return every figure the dashboard needs."""
	if not frappe.has_permission("Job Applicant", "read"):
		frappe.throw(_("You do not have permission to view recruitment data."), frappe.PermissionError)

	days = max(1, min(int(days or 30), 365))
	since = add_days(nowdate(), -days)

	return {
		"kpis": _kpis(since),
		"funnel": _funnel(),
		"by_stage": _by_stage(),
		"score_distribution": _score_distribution(),
		"per_opening": _per_opening(),
		"sources": _sources(),
		"activity": _activity(since, days),
		"period_days": days,
	}


def _count(doctype: str, filters: dict) -> int:
	return frappe.db.count(doctype, filters)


def _kpis(since: str) -> dict[str, Any]:
	total_openings = _count("Job Opening", {})
	active_openings = _count("Job Opening", {"status": "Open"})
	total_applicants = _count("Job Applicant", {})

	return {
		"total_openings": total_openings,
		"active_openings": active_openings,
		"total_applicants": total_applicants,
		"new_applicants": _count("Job Applicant", {"creation": [">=", since]}),
		"shortlisted": _count("Job Applicant", {"status": "Shortlisted"}),
		"interviews": _count("AI Interview", {}),
		"offers": _count("Job Applicant", {"ats_stage": "Offer"}),
		"hired": _count("Job Applicant", {"ats_stage": "Hired"}),
		"rejected": _count("Job Applicant", {"ats_stage": "Rejected"}),
		"scored": _count("AI Candidate Score", {"scoring_status": "Completed"}),
		"parsed": _count("AI Resume Analysis", {"parsing_status": "Completed"}),
		# Guard the division: an empty pipeline must render 0, not blow up.
		"applicants_per_opening": round(total_applicants / active_openings, 1)
		if active_openings
		else 0,
	}


def _group_count(doctype: str, field: str) -> list[dict[str, Any]]:
	"""GROUP BY count via the query builder.

	Frappe v17 rejects raw SQL functions in `get_all(fields=...)`, so aggregates
	go through `frappe.qb`, which is also parameterised end to end.
	"""
	table = frappe.qb.DocType(doctype)
	column = getattr(table, field)
	return (
		frappe.qb.from_(table)
		.select(column.as_("key"), Count("*").as_("count"))
		.groupby(column)
		.orderby(Count("*"), order=frappe.qb.desc)
	).run(as_dict=True)


def _stage_counts() -> dict[str, int]:
	return {r["key"]: r["count"] for r in _group_count("Job Applicant", "ats_stage") if r.get("key")}


def _funnel() -> list[dict[str, Any]]:
	"""Cumulative funnel: each stage counts everyone who reached it or beyond.

	A raw per-stage count is not a funnel - a candidate sitting at 'Offer' has
	necessarily passed 'Applied', so plotting current-stage counts would show a
	misleading sawtooth instead of a monotonically narrowing funnel.
	"""
	counts = _stage_counts()
	order = {stage: i for i, stage in enumerate(FUNNEL_STAGES)}

	reached: dict[str, int] = {stage: 0 for stage in FUNNEL_STAGES}
	for stage, count in counts.items():
		index = order.get(stage)
		if index is None:
			continue  # an exit stage
		for passed in FUNNEL_STAGES[: index + 1]:
			reached[passed] += count

	top = reached[FUNNEL_STAGES[0]] or 0
	return [
		{
			"stage": stage,
			"count": reached[stage],
			"pct": round(reached[stage] / top * 100, 1) if top else 0,
		}
		for stage in FUNNEL_STAGES
	]


def _by_stage() -> list[dict[str, Any]]:
	counts = _stage_counts()
	return [
		{"stage": stage, "count": counts.get(stage, 0)}
		for stage in ATS_STAGES
		if counts.get(stage, 0)
	]


def _score_distribution() -> list[dict[str, Any]]:
	rows = frappe.get_all(
		"AI Candidate Score",
		filters={"scoring_status": "Completed"},
		fields=["overall_score"],
		limit_page_length=0,
	)
	scores = [r["overall_score"] or 0 for r in rows]

	return [
		{"band": label, "count": sum(1 for s in scores if low <= s < high)}
		for label, low, high in SCORE_BANDS
	]


def _per_opening(limit: int = 8) -> list[dict[str, Any]]:
	# `job_title` on Job Applicant is the Link to Job Opening, not free text.
	rows = [r for r in _group_count("Job Applicant", "job_title") if r.get("key")][:limit]
	if not rows:
		return []

	titles = {
		o["name"]: o["job_title"]
		for o in frappe.get_all(
			"Job Opening",
			filters={"name": ["in", [r["key"] for r in rows]]},
			fields=["name", "job_title"],
		)
	}
	return [{"opening": titles.get(r["key"], r["key"]), "count": r["count"]} for r in rows]


def _sources() -> list[dict[str, Any]]:
	return [
		{"source": r["key"] or _("Unspecified"), "count": r["count"]}
		for r in _group_count("Job Applicant", "source")
		if r["count"]
	]


def _activity(since: str, days: int) -> list[dict[str, Any]]:
	"""Applications per day, zero-filled so the line has no false gaps.

	Bucketed in Python rather than with a SQL DATE() expression: the row set is
	bounded by the selected period, and it keeps the query portable.
	"""
	rows = frappe.get_all(
		"Job Applicant",
		filters={"creation": [">=", since]},
		fields=["creation"],
		limit_page_length=0,
	)

	counts: dict[str, int] = {}
	for row in rows:
		day = str(getdate(row["creation"]))
		counts[day] = counts.get(day, 0) + 1

	series = []
	for offset in range(days, -1, -1):
		day = str(getdate(add_days(nowdate(), -offset)))
		series.append({"day": day, "count": counts.get(day, 0)})
	return series
