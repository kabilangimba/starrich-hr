"""AI job description generation (proposal §3).

Returns a draft to the form rather than writing it to the Job Opening. §3 is
explicit that the recruiter reviews and edits before publishing, so the model
never silently mutates a live posting.

This call is synchronous: the recruiter is sitting in front of the form waiting
for the draft, so a background job would only add a round trip.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from ai_hr.ai.prompts import JD_SYSTEM, jd_prompt
from ai_hr.ai.registry import get_provider, require_feature
from ai_hr.ai.schemas import JD_SCHEMA


@frappe.whitelist()
def generate_job_description(job_opening: str) -> dict[str, Any]:
	"""Generate a job description draft for an opening."""
	frappe.has_permission("Job Opening", doc=job_opening, throw=True)
	require_feature("enable_jd_generation")

	opening = frappe.get_doc("Job Opening", job_opening)
	provider = get_provider()
	result = provider.complete_json(JD_SYSTEM, jd_prompt(_render_inputs(opening)), JD_SCHEMA)
	payload = result.as_json()

	return {
		"html": _to_html(payload),
		"sections": payload,
		"provider": result.provider,
		"model": result.model,
		"input_tokens": result.input_tokens,
		"output_tokens": result.output_tokens,
	}


def _render_inputs(opening) -> str:
	"""Collect the recruiter's inputs (§3) into prompt text."""
	skills = getattr(opening, "ai_required_skills", None) or []
	skill_lines = "\n".join(
		f"- {s.skill_name} [{s.importance}]" + (f", minimum {s.min_years:g} years" if s.min_years else "")
		for s in skills
	)

	company = opening.company or ""
	industry = frappe.db.get_value("Company", company, "domain") if company else None

	fields = [
		("Job title", opening.job_title or opening.name),
		("Designation", opening.designation),
		("Company", company),
		("Industry", industry),
		("Department", opening.department),
		("Employment type", opening.employment_type),
		("Location", opening.location),
		("Minimum years of experience", getattr(opening, "ai_min_experience", None)),
		("Education requirement", getattr(opening, "ai_education_requirement", None)),
	]
	lines = [f"{label}: {value}" for label, value in fields if value]

	if skill_lines:
		lines.append(f"Required skills:\n{skill_lines}")

	# Existing copy is context to improve on, not something to preserve verbatim.
	existing = frappe.utils.strip_html(opening.description or "").strip()
	if existing:
		lines.append(f"Existing draft (rewrite and improve):\n{existing}")

	return "\n".join(lines)


def _to_html(payload: dict[str, Any]) -> str:
	"""Render the structured draft as HTML for the Text Editor field."""
	parts: list[str] = []

	if description := payload.get("job_description"):
		parts.append(f"<p>{frappe.utils.escape_html(description)}</p>")

	sections = [
		(_("Responsibilities"), payload.get("responsibilities")),
		(_("Required Qualifications"), payload.get("required_qualifications")),
		(_("Preferred Qualifications"), payload.get("preferred_qualifications")),
		(_("Technical Skills"), payload.get("required_technical_skills")),
		(_("Soft Skills"), payload.get("soft_skills")),
	]
	for heading, items in sections:
		if not items:
			continue
		bullets = "".join(f"<li>{frappe.utils.escape_html(str(i))}</li>" for i in items)
		parts.append(f"<h4>{heading}</h4><ul>{bullets}</ul>")

	if experience := payload.get("experience_requirements"):
		parts.append(f"<h4>{_('Experience')}</h4><p>{frappe.utils.escape_html(experience)}</p>")

	# Interview criteria guide the hiring team; they are not part of the public
	# posting, so they are returned separately rather than inlined above.
	return "".join(parts)
