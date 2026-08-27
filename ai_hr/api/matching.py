"""Candidate/opening matching and scoring (proposal §4, §5).

Scores are advisory. Nothing here changes an applicant's stage or status - §4 is
explicit that rejection and hiring stay with the recruiter.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import frappe
from frappe import _
from frappe.utils import now_datetime

from ai_hr.ai.prompts import MATCH_SYSTEM, match_prompt
from ai_hr.ai.registry import get_provider, require_feature
from ai_hr.ai.schemas import MATCH_SCHEMA

SCORE_DOCTYPE = "AI Candidate Score"
ANALYSIS_DOCTYPE = "AI Resume Analysis"


@frappe.whitelist()
def score_candidate(job_applicant: str, job_opening: str, force: int = 0) -> dict[str, Any]:
	"""Queue scoring of one candidate against one opening."""
	frappe.has_permission("Job Applicant", doc=job_applicant, throw=True)
	require_feature("enable_candidate_matching")

	analysis = _require_analysis(job_applicant)
	opening = frappe.get_doc("Job Opening", job_opening)

	profile_text = _render_profile(analysis)
	role_text = _render_role(opening)
	digest = _fingerprint(profile_text, role_text)

	if not int(force):
		cached = frappe.db.get_value(
			SCORE_DOCTYPE,
			{
				"job_applicant": job_applicant,
				"job_opening": job_opening,
				"source_hash": digest,
				"scoring_status": "Completed",
			},
			"name",
		)
		if cached:
			return {"status": "cached", "score": cached, "message": _("Existing score reused.")}

	score = _upsert_score(job_applicant, job_opening, digest)

	frappe.enqueue(
		"ai_hr.api.matching.run_score",
		queue="long",
		timeout=900,
		job_id=f"ai_hr::score::{score}",
		deduplicate=True,
		score=score,
		profile_text=profile_text,
		role_text=role_text,
	)
	return {"status": "queued", "score": score, "message": _("Scoring started.")}


@frappe.whitelist()
def score_all_for_opening(job_opening: str, force: int = 0) -> dict[str, Any]:
	"""Score every applicant on an opening, so the ranking view has data (§5)."""
	frappe.has_permission("Job Opening", doc=job_opening, throw=True)
	require_feature("enable_candidate_matching")

	# `job_title` is Job Applicant's Link to Job Opening - not a text field.
	applicants = frappe.get_all(
		"Job Applicant", filters={"job_title": job_opening}, pluck="name"
	)

	queued, skipped = [], []
	for applicant in applicants:
		try:
			result = score_candidate(applicant, job_opening, force=force)
			(queued if result["status"] == "queued" else skipped).append(applicant)
		except frappe.ValidationError as exc:
			# Usually "no parsed CV yet" - report it rather than aborting the batch.
			skipped.append(f"{applicant}: {exc}")

	return {
		"total": len(applicants),
		"queued": len(queued),
		"skipped": skipped,
		"message": _("{0} of {1} applicants queued for scoring.").format(len(queued), len(applicants)),
	}


def run_score(score: str, profile_text: str, role_text: str) -> None:
	"""Background worker: score one candidate. Never raises."""
	doc = frappe.get_doc(SCORE_DOCTYPE, score)
	doc.db_set("scoring_status", "Processing", commit=True)

	try:
		provider = get_provider()
		result = provider.complete_json(
			MATCH_SYSTEM, match_prompt(profile_text, role_text), MATCH_SCHEMA
		)
		_apply_scores(doc, result.as_json())

		doc.scoring_status = "Completed"
		doc.error_message = None
		doc.provider_used = result.provider
		doc.model_used = result.model
		doc.input_tokens = result.input_tokens
		doc.output_tokens = result.output_tokens
		doc.scored_on = now_datetime()
		doc.save(ignore_permissions=True)

		# Mirror onto the applicant so it is sortable in the standard list view.
		frappe.db.set_value(
			"Job Applicant",
			doc.job_applicant,
			"ai_match_score",
			doc.overall_score,
			update_modified=False,
		)
		frappe.db.commit()

	except Exception as exc:
		frappe.db.rollback()
		frappe.log_error(title=f"AI HR: scoring failed ({score})", message=frappe.get_traceback())
		frappe.db.set_value(
			SCORE_DOCTYPE,
			score,
			{"scoring_status": "Failed", "error_message": str(exc)[:1000]},
			update_modified=False,
		)
		frappe.db.commit()


# -- helpers ------------------------------------------------------------------


def _require_analysis(job_applicant: str):
	"""Return the applicant's completed CV analysis, or explain why we can't score."""
	name = frappe.db.get_value(
		ANALYSIS_DOCTYPE, {"job_applicant": job_applicant, "parsing_status": "Completed"}, "name"
	)
	if not name:
		frappe.throw(
			_("Parse this candidate's CV before scoring - there is no completed analysis yet.")
		)
	return frappe.get_doc(ANALYSIS_DOCTYPE, name)


def _render_profile(analysis) -> str:
	"""Flatten a stored analysis into the text handed to the model."""
	skills = ", ".join(
		f"{s.skill_name} ({s.years:g}y)" if s.years else s.skill_name for s in analysis.skills
	)
	parts = [
		f"Summary: {analysis.professional_summary or '-'}",
		f"Total years of experience: {analysis.total_years_experience or 0:g}",
		f"Skills: {skills or '-'}",
		f"Experience: {analysis.experience_json or '[]'}",
		f"Education: {analysis.education_json or '[]'}",
		f"Certifications: {analysis.certifications or '-'}",
		f"Languages: {analysis.languages or '-'}",
	]
	return "\n".join(parts)


def _render_role(opening) -> str:
	"""Flatten an opening plus its structured requirements into prompt text."""
	required = getattr(opening, "ai_required_skills", None) or []
	skills = "\n".join(
		f"- {r.skill_name} [{r.importance}]"
		+ (f", minimum {r.min_years:g} years" if r.min_years else "")
		for r in required
	)
	description = frappe.utils.strip_html(opening.description or "").strip()

	parts = [
		f"Job title: {opening.job_title or opening.name}",
		f"Designation: {opening.designation or '-'}",
		f"Department: {opening.department or '-'}",
		f"Employment type: {opening.employment_type or '-'}",
		f"Minimum years of experience: {getattr(opening, 'ai_min_experience', 0) or 0:g}",
		f"Education requirement: {getattr(opening, 'ai_education_requirement', None) or '-'}",
		f"Required skills:\n{skills or '- (none specified)'}",
		f"Description:\n{description or '-'}",
	]
	return "\n".join(parts)


def _fingerprint(profile_text: str, role_text: str) -> str:
	"""Hash both sides, so a score is reused only while neither has changed (§17)."""
	payload = f"{profile_text}\x00{role_text}".encode("utf-8")
	return hashlib.sha256(payload).hexdigest()


def _upsert_score(job_applicant: str, job_opening: str, digest: str) -> str:
	"""One score row per (applicant, opening) pair."""
	existing = frappe.db.get_value(
		SCORE_DOCTYPE, {"job_applicant": job_applicant, "job_opening": job_opening}, "name"
	)
	if existing:
		frappe.db.set_value(
			SCORE_DOCTYPE,
			existing,
			{"source_hash": digest, "scoring_status": "Queued", "error_message": None},
			update_modified=False,
		)
		frappe.db.commit()
		return existing

	doc = frappe.get_doc(
		{
			"doctype": SCORE_DOCTYPE,
			"job_applicant": job_applicant,
			"job_opening": job_opening,
			"source_hash": digest,
			"scoring_status": "Queued",
		}
	).insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.name


def _apply_scores(doc, payload: dict[str, Any]) -> None:
	"""Map the model's JSON onto the score document, clamping to 0-100."""
	for field in (
		"overall_score",
		"skills_score",
		"experience_score",
		"education_score",
		"certification_score",
		"requirements_score",
	):
		setattr(doc, field, _clamp(payload.get(field)))

	doc.verdict = payload.get("verdict")
	doc.explanation = payload.get("explanation")
	doc.recommended_action = payload.get("recommended_action")
	doc.matched_requirements = _as_lines(payload.get("matched_requirements"))
	doc.missing_requirements = _as_lines(payload.get("missing_requirements"))


def _clamp(value: Any) -> float:
	"""Coerce to a 0-100 float.

	A model can return a stray 0-1 ratio, a string, or a number above 100; a
	Percent field would happily store nonsense and corrupt the ranking.
	"""
	try:
		number = float(value)
	except (TypeError, ValueError):
		return 0.0
	return round(max(0.0, min(100.0, number)), 2)


def _as_lines(values: Any) -> str | None:
	if not values:
		return None
	return "\n".join(f"- {str(v).strip()}" for v in values if str(v).strip())
