"""Recruiter chat assistant (proposal §8).

Two steps, deliberately:

1. **Plan** - the model turns the question into constrained parameters
   (`ASSISTANT_QUERY_SCHEMA`).
2. **Retrieve and answer** - this app runs a permission-checked ORM query and
   hands only those records back to the model to phrase an answer.

The model never sees a database connection and never emits SQL, so a prompt
injection in a CV cannot widen data access - the worst it can do is request a
different filter, which still runs under the reading user's permissions (§15).

This also keeps the provider abstraction intact: native tool-use APIs differ per
vendor, whereas two structured calls work identically on all four providers.
"""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _

from ai_hr.ai.base import AIProviderError
from ai_hr.ai.prompts import ANSWER_SYSTEM, PLANNER_SYSTEM, answer_prompt, planner_prompt
from ai_hr.ai.registry import get_provider
from ai_hr.ai.schemas import ASSISTANT_QUERY_SCHEMA

#: Hard ceiling on rows handed to the model, whatever the question asks for.
#: Bounds both token spend and how much data one answer can expose.
MAX_ROWS = 25
DEFAULT_ROWS = 10


@frappe.whitelist()
def ask(question: str) -> dict[str, Any]:
	"""Answer a recruiter's question from HR data."""
	if not (question or "").strip():
		frappe.throw(_("Ask a question first."))

	# Reading candidate data requires permission on the doctype itself; the
	# per-record queries below are additionally permission-filtered by Frappe.
	if not frappe.has_permission("Job Applicant", "read"):
		frappe.throw(_("You do not have permission to read candidate data."), frappe.PermissionError)

	_require_configured()
	provider = get_provider()

	# A bare `raise` carries the class name to the client but not the message,
	# so the UI ends up showing "AIProviderError". `frappe.throw` populates
	# _server_messages, which is what the browser actually reads.
	try:
		plan_result = provider.complete_json(
			PLANNER_SYSTEM, planner_prompt(question), ASSISTANT_QUERY_SCHEMA
		)
		plan = plan_result.as_json()
	except AIProviderError as exc:
		frappe.throw(str(exc), title=_("AI provider error"))

	if plan.get("intent") == "unsupported":
		return {
			"answer": _("I can only answer questions about candidates and job openings."),
			"rows": 0,
			"intent": "unsupported",
		}

	records = _retrieve(plan)
	if not records:
		return {
			"answer": _("No records matched that question."),
			"rows": 0,
			"intent": plan.get("intent"),
		}

	try:
		answer_result = provider.complete(
			ANSWER_SYSTEM, answer_prompt(question, json.dumps(records, indent=2, default=str))
		)
	except AIProviderError as exc:
		frappe.throw(str(exc), title=_("AI provider error"))

	return {
		"answer": answer_result.text.strip(),
		"rows": len(records),
		"intent": plan.get("intent"),
		"provider": answer_result.provider,
		"model": answer_result.model,
		"input_tokens": plan_result.input_tokens + answer_result.input_tokens,
		"output_tokens": plan_result.output_tokens + answer_result.output_tokens,
	}


def _require_configured() -> None:
	"""Fail with an actionable message when no provider credential is set.

	Without this the failure surfaces from inside the vendor SDK on the first
	call, which reads as a bug rather than as configuration the admin still owes.
	"""
	from ai_hr.ai.registry import get_settings

	settings = get_settings()
	if settings.provider == "Ollama":
		return  # runs locally, no credential

	if not settings.get_password("api_key", raise_exception=False):
		frappe.throw(
			_(
				"No API key is set for {0}. Open <b>AI HR Settings</b> and add one, "
				"then ask again."
			).format(settings.provider or _("the configured provider")),
			title=_("AI provider not configured"),
		)


# -- retrieval ----------------------------------------------------------------


def _retrieve(plan: dict[str, Any]) -> list[dict[str, Any]]:
	"""Run the planned query under the current user's permissions."""
	limit = _row_limit(plan.get("limit"))
	opening = _resolve_opening(plan.get("job_opening_hint"))

	filters: dict[str, Any] = {"scoring_status": "Completed"}
	if opening:
		filters["job_opening"] = opening
	if plan.get("min_score") is not None:
		filters["overall_score"] = [">=", float(plan["min_score"])]

	scores = frappe.get_all(
		"AI Candidate Score",
		filters=filters,
		fields=[
			"job_applicant",
			"job_opening",
			"overall_score",
			"verdict",
			"skills_score",
			"experience_score",
			"explanation",
			"missing_requirements",
		],
		order_by="overall_score desc",
		# Fetch a margin, because post-filters below can discard rows.
		limit_page_length=MAX_ROWS * 3,
	)

	rows = [_hydrate(s) for s in scores]
	rows = [r for r in rows if r]

	rows = _apply_post_filters(rows, plan)
	return rows[:limit]


def _apply_post_filters(rows: list[dict], plan: dict[str, Any]) -> list[dict]:
	"""Apply filters that cannot be expressed as simple ORM conditions."""
	skills = [s.lower() for s in (plan.get("skills") or []) if s]
	if skills:
		rows = [
			r
			for r in rows
			if all(any(skill in owned for owned in r["skills_lower"]) for skill in skills)
		]

	if (min_years := plan.get("min_years_experience")) is not None:
		rows = [r for r in rows if (r.get("total_years_experience") or 0) >= float(min_years)]

	if missing := (plan.get("missing_requirement") or "").strip().lower():
		rows = [r for r in rows if missing in (r.get("missing_requirements") or "").lower()]

	if names := [n.lower() for n in (plan.get("candidate_hints") or []) if n]:
		matched = [r for r in rows if any(n in (r.get("applicant_name") or "").lower() for n in names)]
		# Only narrow when the names actually matched something, so a misheard
		# name does not silently return an empty answer.
		if matched:
			rows = matched

	for row in rows:
		row.pop("skills_lower", None)
	return rows


def _hydrate(score: dict[str, Any]) -> dict[str, Any] | None:
	"""Attach candidate and profile detail to a score row."""
	applicant = frappe.db.get_value(
		"Job Applicant",
		score["job_applicant"],
		["applicant_name", "ats_stage", "status"],
		as_dict=True,
	)
	if not applicant:
		return None

	analysis_name = frappe.db.get_value(
		"AI Resume Analysis",
		{"job_applicant": score["job_applicant"], "parsing_status": "Completed"},
		"name",
	)

	skills: list[str] = []
	profile: dict[str, Any] = {}
	if analysis_name:
		analysis = frappe.get_doc("AI Resume Analysis", analysis_name)
		skills = [s.skill_name for s in analysis.skills]
		profile = {
			"total_years_experience": analysis.total_years_experience,
			"location": analysis.location,
			"certifications": analysis.certifications,
		}

	return {
		**score,
		**profile,
		"applicant_name": applicant.applicant_name,
		"ats_stage": applicant.ats_stage,
		"skills": skills,
		"skills_lower": [s.lower() for s in skills],
	}


def _resolve_opening(hint: str | None) -> str | None:
	"""Map a free-text opening reference onto a real Job Opening name."""
	hint = (hint or "").strip()
	if not hint:
		return None

	if frappe.db.exists("Job Opening", hint):
		return hint

	match = frappe.get_all(
		"Job Opening",
		or_filters={"job_title": ["like", f"%{hint}%"], "name": ["like", f"%{hint}%"]},
		pluck="name",
		limit_page_length=1,
	)
	return match[0] if match else None


def _row_limit(requested: Any) -> int:
	try:
		value = int(requested)
	except (TypeError, ValueError):
		return DEFAULT_ROWS
	return max(1, min(value, MAX_ROWS))
