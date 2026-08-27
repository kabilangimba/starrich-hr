"""JSON Schemas for structured AI output.

Authored for the strictest consumer: OpenAI's `strict` mode requires every
property to appear in `required` and `additionalProperties: false` throughout.
Optional values are therefore expressed as nullable types rather than by
omitting them from `required`.

Claude accepts this shape as-is. Gemini does not: its `types.Schema` takes a
single type plus a `nullable` flag and rejects both `["string", "null"]` and
`additionalProperties`, so the Gemini adapter translates these schemas on the
way out (see ai_hr.ai.providers.gemini_provider.to_gemini_schema).
"""

from __future__ import annotations

from typing import Any


def _string(description: str, nullable: bool = True) -> dict[str, Any]:
	return {
		"type": ["string", "null"] if nullable else "string",
		"description": description,
	}


def _array(items: dict[str, Any], description: str) -> dict[str, Any]:
	return {"type": "array", "items": items, "description": description}


def _object(properties: dict[str, Any]) -> dict[str, Any]:
	"""Object with every key required and no extras - strict-mode compatible."""
	return {
		"type": "object",
		"properties": properties,
		"required": list(properties),
		"additionalProperties": False,
	}


EXPERIENCE_ITEM = _object(
	{
		"company": _string("Employer name."),
		"job_title": _string("Role held at that employer."),
		"start_date": _string("Start date as written on the CV, e.g. 'Jan 2022'."),
		"end_date": _string("End date as written, or 'Present' if current."),
		"summary": _string("One or two sentences on what the candidate did."),
	}
)

EDUCATION_ITEM = _object(
	{
		"institution": _string("School, college or university."),
		"qualification": _string("Degree or certificate obtained."),
		"field_of_study": _string("Subject area."),
		"year": _string("Completion year as written on the CV."),
	}
)

SKILL_ITEM = _object(
	{
		"name": _string("The skill exactly as a recruiter would search for it.", nullable=False),
		"category": {
			"type": "string",
			"enum": ["Technical", "Soft", "Language", "Tool"],
			"description": "Which bucket the skill belongs to.",
		},
		"years": {
			"type": ["number", "null"],
			"description": "Years of experience with this skill if the CV states or implies it.",
		},
	}
)

#: Contract for CV parsing (proposal §2).
RESUME_SCHEMA = _object(
	{
		"full_name": _string("Candidate's full name."),
		"email": _string("Primary email address."),
		"phone": _string("Primary phone number, digits and separators as written."),
		"location": _string("City and country of residence."),
		"professional_summary": _string("Two to three sentence profile of the candidate."),
		"total_years_experience": {
			"type": ["number", "null"],
			"description": "Total professional experience in years. Estimate from the roles listed.",
		},
		"skills": _array(SKILL_ITEM, "Every skill evidenced by the CV."),
		"experience": _array(EXPERIENCE_ITEM, "Employment history, most recent first."),
		"education": _array(EDUCATION_ITEM, "Academic history."),
		"certifications": _array(
			_string("Certification name, with issuing body if stated.", nullable=False),
			"Professional certifications.",
		),
		"languages": _array(
			_string("A spoken or written language.", nullable=False),
			"Human languages the candidate speaks.",
		),
		"projects": _array(
			_string("Project name and a short description.", nullable=False),
			"Notable projects described on the CV.",
		),
		"linkedin_url": _string("LinkedIn profile URL."),
		"github_url": _string("GitHub profile URL."),
		"portfolio_url": _string("Personal site or portfolio URL."),
	}
)


#: Contract for candidate/opening matching (proposal §4).
MATCH_SCHEMA = _object(
	{
		"overall_score": {
			"type": "number",
			"description": "Overall fit from 0 to 100.",
		},
		"skills_score": {"type": "number", "description": "Skills fit, 0 to 100."},
		"experience_score": {"type": "number", "description": "Experience fit, 0 to 100."},
		"education_score": {"type": "number", "description": "Education fit, 0 to 100."},
		"certification_score": {"type": "number", "description": "Certification fit, 0 to 100."},
		"requirements_score": {
			"type": "number",
			"description": "Fit against the stated job requirements, 0 to 100.",
		},
		"verdict": {
			"type": "string",
			"enum": ["Strong Match", "Good Match", "Possible Match", "Weak Match"],
			"description": "Banded summary of overall_score.",
		},
		"explanation": _string(
			"Two to four sentences justifying the score, citing evidence from the CV.",
			nullable=False,
		),
		"matched_requirements": _array(
			_string("A job requirement the candidate demonstrably meets.", nullable=False),
			"Requirements the candidate satisfies.",
		),
		"missing_requirements": _array(
			_string("A job requirement with no supporting evidence on the CV.", nullable=False),
			"Requirements the candidate does not evidence.",
		),
		"recommended_action": _string(
			"A suggested next step for the recruiter. Advisory only - never a hiring decision.",
			nullable=False,
		),
	}
)


_BULLETS = lambda desc: _array(_string("One item.", nullable=False), desc)  # noqa: E731


#: Contract for job description generation (proposal §3).
JD_SCHEMA = _object(
	{
		"job_description": _string(
			"Two or three paragraphs introducing the role and the team.", nullable=False
		),
		"responsibilities": _BULLETS("What the person will actually do, day to day."),
		"required_qualifications": _BULLETS("Must-haves. Keep this list genuinely essential."),
		"preferred_qualifications": _BULLETS("Nice-to-haves that would strengthen an application."),
		"required_technical_skills": _BULLETS("Technical skills needed to do the job."),
		"soft_skills": _BULLETS("Interpersonal and working-style skills that matter for this role."),
		"experience_requirements": _string(
			"Experience expected, stated as a range with the kind of work that counts.",
			nullable=False,
		),
		"suggested_interview_criteria": _BULLETS(
			"What an interviewer should assess to test fit for this role."
		),
	}
)


INTERVIEW_QUESTION = _object(
	{
		"question": _string("The question to ask, phrased as it would be spoken.", nullable=False),
		"category": {
			"type": "string",
			"enum": ["Technical", "Behavioural", "Situational", "Experience", "Culture"],
			"description": "What kind of question this is.",
		},
		"rationale": _string(
			"Why this question is worth asking this candidate for this role.", nullable=False
		),
		"look_for": _string("What a strong answer would contain.", nullable=False),
	}
)


#: Contract for interview question generation (proposal §6).
INTERVIEW_QUESTIONS_SCHEMA = _object(
	{
		"questions": _array(INTERVIEW_QUESTION, "Questions tailored to this candidate and role."),
		"focus_areas": _BULLETS(
			"Topics worth probing, typically where the CV is thin or ambiguous."
		),
	}
)


#: Contract for the recruiter assistant's query planning step (proposal §8).
#:
#: The model translates a natural-language question into these constrained
#: parameters; the app then runs a permission-checked ORM query. The model never
#: sees or writes SQL, so a prompt injection cannot widen data access (§15).
ASSISTANT_QUERY_SCHEMA = _object(
	{
		"intent": {
			"type": "string",
			"enum": [
				"rank_candidates",
				"search_candidates",
				"compare_candidates",
				"summarise_opening",
				"unsupported",
			],
			"description": "What the recruiter is asking for.",
		},
		"job_opening_hint": _string(
			"The job title or opening the question refers to, as the user wrote it."
		),
		"candidate_hints": _array(
			_string("A candidate name mentioned in the question.", nullable=False),
			"Candidate names referenced, for comparison questions.",
		),
		"skills": _array(
			_string("A skill to filter on.", nullable=False),
			"Skills the candidate must have.",
		),
		"min_years_experience": {
			"type": ["number", "null"],
			"description": "Minimum total years of experience, if the question implies one.",
		},
		"min_score": {
			"type": ["number", "null"],
			"description": "Minimum AI match score from 0 to 100, if implied.",
		},
		"missing_requirement": _string(
			"A requirement the question asks who is *missing*, e.g. 'AWS certification'."
		),
		"limit": {
			"type": ["integer", "null"],
			"description": "How many results the question asks for.",
		},
	}
)


#: Contract for post-interview evaluation (proposal §7).
INTERVIEW_EVALUATION_SCHEMA = _object(
	{
		"summary": _string("A short summary of how the interview went.", nullable=False),
		"strengths": _BULLETS("Strengths the candidate demonstrated in the interview."),
		"weaknesses": _BULLETS("Weaknesses or gaps that showed up."),
		"skills_demonstrated": _BULLETS("Skills evidenced by the candidate's answers."),
		"areas_of_concern": _BULLETS("Anything a recruiter should follow up on."),
		"recommended_next_step": _string(
			"A suggested next step. Advisory only - never a hire or reject decision.",
			nullable=False,
		),
	}
)
