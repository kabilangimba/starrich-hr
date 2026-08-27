"""AI interview assistant and evaluation (proposal §6, §7).

Question generation is tailored to the specific candidate and role; evaluation
summarises the interviewer's own notes. Both are advisory - neither writes a
hiring decision anywhere (§7).
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from ai_hr.ai.prompts import (
	EVALUATION_SYSTEM,
	INTERVIEW_SYSTEM,
	interview_evaluation_prompt,
	interview_questions_prompt,
)
from ai_hr.ai.registry import get_provider, require_feature
from ai_hr.ai.schemas import INTERVIEW_EVALUATION_SCHEMA, INTERVIEW_QUESTIONS_SCHEMA
from ai_hr.api.matching import _render_profile, _render_role

INTERVIEW_DOCTYPE = "AI Interview"
ANALYSIS_DOCTYPE = "AI Resume Analysis"

#: Kept modest: a recruiter edits this list by hand, and an over-long list is
#: less useful than a focused one.
DEFAULT_QUESTION_COUNT = 8
MAX_QUESTION_COUNT = 20


@frappe.whitelist()
def generate_questions(ai_interview: str, count: int = DEFAULT_QUESTION_COUNT) -> dict[str, Any]:
	"""Generate interview questions for a candidate and role (§6).

	Replaces only AI-generated rows; anything the recruiter added by hand is kept.
	"""
	frappe.has_permission(INTERVIEW_DOCTYPE, doc=ai_interview, throw=True)
	require_feature("enable_interview_assistant")

	count = max(1, min(int(count or DEFAULT_QUESTION_COUNT), MAX_QUESTION_COUNT))
	doc = frappe.get_doc(INTERVIEW_DOCTYPE, ai_interview)

	profile_text = _profile_for(doc.job_applicant)
	role_text = _role_for(doc.job_opening)

	try:
		provider = get_provider()
		result = provider.complete_json(
			INTERVIEW_SYSTEM,
			interview_questions_prompt(profile_text, role_text, doc.interview_type, count),
			INTERVIEW_QUESTIONS_SCHEMA,
		)
		payload = result.as_json()
	except Exception as exc:
		doc.db_set({"status": "Failed", "error_message": str(exc)[:1000]})
		frappe.db.commit()
		raise

	# Preserve recruiter-authored questions: only rows that carry a rationale
	# came from the model, so anything without one was added by hand.
	manual = [q for q in doc.questions if not q.rationale]
	doc.set("questions", [])

	generated = 0
	for item in payload.get("questions") or []:
		question = (item.get("question") or "").strip()
		if not question:
			continue
		generated += 1
		doc.append(
			"questions",
			{
				"question": question,
				"category": item.get("category") or "Technical",
				"rationale": item.get("rationale"),
				"look_for": item.get("look_for"),
			},
		)

	for row in manual:
		doc.append(
			"questions",
			{"question": row.question, "category": row.category, "look_for": row.look_for},
		)

	doc.focus_areas = _as_lines(payload.get("focus_areas"))
	doc.status = "Questions Generated"
	doc.error_message = None
	_stamp_run(doc, result)
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	return {
		"status": "ok",
		# The count of rows actually added, not the raw payload length - a model
		# can return blank entries, and reporting those as generated is a lie.
		"generated": generated,
		"kept_manual": len(manual),
		"message": _("{0} questions generated.").format(generated),
	}


@frappe.whitelist()
def evaluate_interview(ai_interview: str) -> dict[str, Any]:
	"""Summarise a completed interview from the interviewer's notes (§7)."""
	frappe.has_permission(INTERVIEW_DOCTYPE, doc=ai_interview, throw=True)
	require_feature("enable_interview_assistant")

	doc = frappe.get_doc(INTERVIEW_DOCTYPE, ai_interview)
	if not (doc.interview_notes or "").strip():
		frappe.throw(_("Add interview notes before asking for an evaluation."))

	role_text = _role_for(doc.job_opening)

	try:
		provider = get_provider()
		result = provider.complete_json(
			EVALUATION_SYSTEM,
			interview_evaluation_prompt(role_text, doc.interview_notes, doc.ratings or ""),
			INTERVIEW_EVALUATION_SCHEMA,
		)
		payload = result.as_json()
	except Exception as exc:
		doc.db_set({"status": "Failed", "error_message": str(exc)[:1000]})
		frappe.db.commit()
		raise

	doc.ai_summary = payload.get("summary")
	doc.strengths = _as_lines(payload.get("strengths"))
	doc.weaknesses = _as_lines(payload.get("weaknesses"))
	doc.skills_demonstrated = _as_lines(payload.get("skills_demonstrated"))
	doc.areas_of_concern = _as_lines(payload.get("areas_of_concern"))
	doc.recommended_next_step = payload.get("recommended_next_step")
	doc.status = "Evaluated"
	doc.error_message = None
	_stamp_run(doc, result)
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	return {"status": "ok", "message": _("Interview evaluated.")}


# -- helpers ------------------------------------------------------------------


def _profile_for(job_applicant: str) -> str:
	"""Prefer the parsed CV; fall back to the applicant record.

	An interview can legitimately be prepared before a CV has been parsed, so this
	degrades to basic details rather than blocking the recruiter.
	"""
	name = frappe.db.get_value(
		ANALYSIS_DOCTYPE, {"job_applicant": job_applicant, "parsing_status": "Completed"}, "name"
	)
	if name:
		return _render_profile(frappe.get_doc(ANALYSIS_DOCTYPE, name))

	applicant = frappe.get_doc("Job Applicant", job_applicant)
	return "\n".join(
		[
			f"Name: {applicant.applicant_name or '-'}",
			f"Designation applied for: {applicant.designation or '-'}",
			f"Cover letter: {frappe.utils.strip_html(applicant.cover_letter or '').strip() or '-'}",
			"(No parsed CV is available for this candidate.)",
		]
	)


def _role_for(job_opening: str | None) -> str:
	if not job_opening:
		return "(No job opening linked to this interview.)"
	return _render_role(frappe.get_doc("Job Opening", job_opening))


def _stamp_run(doc, result) -> None:
	doc.provider_used = result.provider
	doc.model_used = result.model
	doc.input_tokens = result.input_tokens
	doc.output_tokens = result.output_tokens


def _as_lines(values: Any) -> str | None:
	if not values:
		return None
	return "\n".join(f"- {str(v).strip()}" for v in values if str(v).strip())
