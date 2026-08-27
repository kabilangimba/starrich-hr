"""CV parsing pipeline (proposal §2, §16, §17).

Flow: recruiter uploads a CV -> extract text -> background job -> AI provider ->
structured profile stored on `AI Resume Analysis`.

Parsing runs in a background job because a provider call takes seconds to
minutes; uploading a CV must never block the form (§16). Identical CV text is
never sent to the provider twice (§17).
"""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _
from frappe.utils import now_datetime

from ai_hr.ai.prompts import RESUME_SYSTEM, resume_prompt
from ai_hr.ai.registry import get_provider, require_feature
from ai_hr.ai.schemas import RESUME_SCHEMA
from ai_hr.utils.extract import content_hash, extract_text

ANALYSIS_DOCTYPE = "AI Resume Analysis"


@frappe.whitelist()
def parse_resume(job_applicant: str, force: int = 0) -> dict[str, Any]:
	"""Queue CV parsing for a Job Applicant.

	Returns immediately with the queued/cached state; the caller polls or listens
	for the realtime event rather than waiting on the provider.
	"""
	frappe.has_permission("Job Applicant", doc=job_applicant, throw=True)
	require_feature("enable_resume_parsing")

	applicant = frappe.get_doc("Job Applicant", job_applicant)
	if not applicant.resume_attachment:
		frappe.throw(_("This applicant has no resume attached."))

	# Extract synchronously: it is fast, and it means an unreadable file is
	# reported to the recruiter now rather than failing silently in a worker.
	text = extract_text(applicant.resume_attachment)
	digest = content_hash(text)

	cached = _find_cached(job_applicant, digest) if not int(force) else None
	if cached:
		_stamp_applicant(job_applicant, cached, "Completed")
		frappe.db.commit()
		return {"status": "cached", "analysis": cached, "message": _("Existing analysis reused.")}

	analysis = _upsert_analysis(job_applicant, applicant.resume_attachment, digest)
	_stamp_applicant(job_applicant, analysis, "Queued")
	frappe.db.commit()

	frappe.enqueue(
		"ai_hr.api.resume.run_parse",
		queue="long",
		timeout=900,
		job_id=f"ai_hr::parse::{analysis}",
		deduplicate=True,
		analysis=analysis,
		cv_text=text,
	)

	return {"status": "queued", "analysis": analysis, "message": _("Parsing started.")}


def auto_parse_on_insert(doc, method=None) -> None:
	"""Queue CV parsing as soon as an applicant is created.

	Hooked on Job Applicant `after_insert`, so a candidate applying through the
	public web form is parsed without anyone pressing a button.

	Everything here is deliberately defensive, because this runs *inside the
	candidate's own submission*: an unconfigured provider, a disabled feature or
	an unreadable PDF must never turn into an error on their screen. Nothing is
	raised, and no work is done inline - even text extraction happens in the
	worker, so the form returns immediately.
	"""
	try:
		if not doc.get("resume_attachment"):
			return

		# Checked without require_feature(), which raises; a disabled toggle is a
		# reason to skip quietly, not to fail the application.
		from ai_hr.ai.registry import get_settings

		if not get_settings().get("enable_resume_parsing"):
			return

		frappe.enqueue(
			"ai_hr.api.resume.run_auto_parse",
			queue="long",
			timeout=900,
			job_id=f"ai_hr::autoparse::{doc.name}",
			deduplicate=True,
			# The worker must not start before the row is committed, or it will
			# look up an applicant that does not exist yet.
			enqueue_after_commit=True,
			job_applicant=doc.name,
		)
	except Exception:
		frappe.log_error(
			title="AI HR: could not queue automatic CV parse",
			message=frappe.get_traceback(),
		)


def run_auto_parse(job_applicant: str) -> None:
	"""Background worker for `auto_parse_on_insert`.

	Runs as Administrator: the applicant who triggered it may be Guest, and this
	is a system-initiated action rather than something the submitter is doing.
	"""
	frappe.set_user("Administrator")

	try:
		applicant = frappe.get_doc("Job Applicant", job_applicant)
		if not applicant.resume_attachment:
			return

		text = extract_text(applicant.resume_attachment)
		digest = content_hash(text)

		cached = _find_cached(job_applicant, digest)
		if cached:
			_stamp_applicant(job_applicant, cached, "Completed")
			frappe.db.commit()
			return

		analysis = _upsert_analysis(job_applicant, applicant.resume_attachment, digest)
		_stamp_applicant(job_applicant, analysis, "Queued")
		frappe.db.commit()

		run_parse(analysis, text)
	except Exception:
		# The applicant is already saved; a parsing failure must not undo that.
		frappe.db.rollback()
		frappe.log_error(
			title=f"AI HR: automatic CV parse failed for {job_applicant}",
			message=frappe.get_traceback(),
		)


def run_parse(analysis: str, cv_text: str) -> None:
	"""Background worker: call the provider and store the profile.

	Never raises - a failure is recorded on the document so the recruiter can see
	why, rather than vanishing into the worker log.
	"""
	doc = frappe.get_doc(ANALYSIS_DOCTYPE, analysis)
	doc.db_set("parsing_status", "Processing", commit=True)

	try:
		provider = get_provider()
		result = provider.complete_json(RESUME_SYSTEM, resume_prompt(cv_text), RESUME_SCHEMA)
		_apply_profile(doc, result.as_json())

		doc.parsing_status = "Completed"
		doc.error_message = None
		doc.provider_used = result.provider
		doc.model_used = result.model
		doc.input_tokens = result.input_tokens
		doc.output_tokens = result.output_tokens
		doc.analysis_date = now_datetime()
		doc.save(ignore_permissions=True)
		frappe.db.commit()

	except Exception as exc:
		frappe.db.rollback()
		frappe.log_error(title=f"AI HR: CV parsing failed ({analysis})", message=frappe.get_traceback())
		frappe.db.set_value(
			ANALYSIS_DOCTYPE,
			analysis,
			{"parsing_status": "Failed", "error_message": str(exc)[:1000]},
			update_modified=False,
		)
		frappe.db.commit()

	_notify(doc.job_applicant, analysis)


# -- helpers ------------------------------------------------------------------


def _find_cached(job_applicant: str, digest: str) -> str | None:
	"""Return a completed analysis for identical CV text, if one exists (§17)."""
	return frappe.db.get_value(
		ANALYSIS_DOCTYPE,
		{"job_applicant": job_applicant, "content_hash": digest, "parsing_status": "Completed"},
		"name",
	)


def _upsert_analysis(job_applicant: str, file_url: str, digest: str) -> str:
	"""Reuse this applicant's analysis row if present, else create one.

	One row per applicant keeps the Job Applicant form's link unambiguous; a new
	CV overwrites the previous profile rather than accumulating rows.
	"""
	existing = frappe.db.get_value(ANALYSIS_DOCTYPE, {"job_applicant": job_applicant}, "name")

	if existing:
		frappe.db.set_value(
			ANALYSIS_DOCTYPE,
			existing,
			{
				"resume_file": file_url,
				"content_hash": digest,
				"parsing_status": "Queued",
				"error_message": None,
			},
			update_modified=False,
		)
		frappe.db.commit()
		return existing

	doc = frappe.get_doc(
		{
			"doctype": ANALYSIS_DOCTYPE,
			"job_applicant": job_applicant,
			"resume_file": file_url,
			"content_hash": digest,
			"parsing_status": "Queued",
		}
	).insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.name


def _apply_profile(doc, profile: dict[str, Any]) -> None:
	"""Map the provider's JSON onto the document.

	Uses `.get` throughout: a provider may omit a key despite the schema, and a
	missing optional field must not lose the rest of a successful parse.
	"""
	doc.full_name = profile.get("full_name")
	doc.email_id = profile.get("email")
	doc.phone = profile.get("phone")
	doc.location = profile.get("location")
	doc.professional_summary = profile.get("professional_summary")
	doc.total_years_experience = profile.get("total_years_experience") or 0
	doc.linkedin_url = profile.get("linkedin_url")
	doc.github_url = profile.get("github_url")
	doc.portfolio_url = profile.get("portfolio_url")

	doc.experience_json = json.dumps(profile.get("experience") or [], indent=2)
	doc.education_json = json.dumps(profile.get("education") or [], indent=2)
	doc.certifications = _as_lines(profile.get("certifications"))
	doc.languages = _as_lines(profile.get("languages"))
	doc.projects = _as_lines(profile.get("projects"))

	doc.set("skills", [])
	seen: set[str] = set()
	for skill in profile.get("skills") or []:
		name = (skill.get("name") or "").strip()
		# Providers sometimes emit the same skill twice under different casing;
		# duplicates would skew the skills match score later.
		if not name or name.lower() in seen:
			continue
		seen.add(name.lower())
		doc.append(
			"skills",
			{
				"skill_name": name[:140],
				"category": skill.get("category") or "Technical",
				"years": skill.get("years") or 0,
			},
		)


def _as_lines(values: Any) -> str | None:
	"""Render a list of strings as newline-separated text for a Small Text field."""
	if not values:
		return None
	return "\n".join(str(v).strip() for v in values if str(v).strip())


def _stamp_applicant(job_applicant: str, analysis: str, status: str) -> None:
	"""Mirror the analysis link and status onto the Job Applicant.

	Written with `db.set_value` and `update_modified=False` so a background parse
	does not bump the applicant's modified timestamp or trip a concurrent-edit
	warning for a recruiter who has the form open.
	"""
	frappe.db.set_value(
		"Job Applicant",
		job_applicant,
		{"ai_resume_analysis": analysis, "ai_parsing_status": status},
		update_modified=False,
	)


def _notify(job_applicant: str, analysis: str) -> None:
	"""Push the result to any open form for this applicant."""
	status = frappe.db.get_value(ANALYSIS_DOCTYPE, analysis, "parsing_status")
	_stamp_applicant(job_applicant, analysis, status)
	frappe.db.commit()
	frappe.publish_realtime(
		"ai_hr_resume_parsed",
		{"job_applicant": job_applicant, "analysis": analysis, "status": status},
		doctype="Job Applicant",
		docname=job_applicant,
	)
