"""Demo data for Frappe HR + AI HR.

Seeds a realistic recruitment pipeline so every feature has something to show:
HR foundation (company, departments, designations, branches, employees), job
openings with structured requirements, applicants spread across the ATS
pipeline, plus AI resume analyses, candidate scores and interviews.

The AI records here are **synthetic, not generated** - no provider is called, so
this runs with no API key configured.

    bench --site your-site execute ai_hr.demo.make_demo_data
    bench --site your-site execute ai_hr.demo.clear_demo_data

Everything created is tagged so `clear_demo_data` can remove exactly what this
module made and nothing else.
"""

from __future__ import annotations

import random
from typing import Any

import frappe
from frappe.utils import add_days, nowdate

#: Every demo applicant uses this domain, so cleanup is unambiguous.
DEMO_DOMAIN = "@demo.aihr.test"
DEMO_COMPANY = "Starrich International"
DEMO_ABBR = "SIL"

DEPARTMENTS = ["Engineering", "Product", "Sales", "Finance", "People Operations"]

DESIGNATIONS = [
	"Senior Software Engineer",
	"Backend Engineer",
	"Frontend Engineer",
	"Product Manager",
	"Sales Executive",
	"Accountant",
	"HR Officer",
]

BRANCHES = ["Dar es Salaam", "Arusha", "Mwanza"]

EMPLOYMENT_TYPES = ["Full-time", "Contract", "Intern"]

# -- openings -----------------------------------------------------------------

OPENINGS = [
	{
		"title": "Senior Backend Engineer",
		"designation": "Senior Software Engineer",
		"department": "Engineering",
		"branch": "Dar es Salaam",
		"min_experience": 5,
		"education": "BSc in Computer Science, Software Engineering or equivalent experience",
		"vacancies": 2,
		"skills": [
			("Python", "Required", 5),
			("Django", "Required", 4),
			("PostgreSQL", "Required", 3),
			("Docker", "Preferred", 0),
			("AWS", "Preferred", 0),
		],
		"description": (
			"<p>We are looking for a senior backend engineer to own our core services "
			"as we scale across East Africa.</p>"
		),
	},
	{
		"title": "Frontend Engineer",
		"designation": "Frontend Engineer",
		"department": "Engineering",
		"branch": "Dar es Salaam",
		"min_experience": 3,
		"education": "Degree in a technical field or demonstrable portfolio",
		"vacancies": 1,
		"skills": [
			("React", "Required", 3),
			("TypeScript", "Required", 2),
			("CSS", "Required", 3),
			("Figma", "Preferred", 0),
		],
		"description": "<p>Build the interfaces our customers use every day.</p>",
	},
	{
		"title": "Product Manager",
		"designation": "Product Manager",
		"department": "Product",
		"branch": "Dar es Salaam",
		"min_experience": 4,
		"education": "Bachelor's degree in any discipline",
		"vacancies": 1,
		"skills": [
			("Product Strategy", "Required", 4),
			("User Research", "Required", 2),
			("SQL", "Preferred", 0),
		],
		"description": "<p>Own the roadmap for our payments product line.</p>",
	},
	{
		"title": "Sales Executive",
		"designation": "Sales Executive",
		"department": "Sales",
		"branch": "Arusha",
		"min_experience": 2,
		"education": "Diploma or degree in Business, Marketing or related",
		"vacancies": 3,
		"skills": [
			("B2B Sales", "Required", 2),
			("CRM", "Required", 1),
			("Swahili", "Required", 0),
		],
		"description": "<p>Grow our merchant base across the northern circuit.</p>",
	},
]

# -- candidates ---------------------------------------------------------------
#
# (name, opening index, ats_stage, years, score, skills, location, source)
CANDIDATES = [
	("Amina Hassan", 0, "Offer", 8, 94, ["Python", "Django", "PostgreSQL", "Docker", "AWS"], "Dar es Salaam", None),
	("Joseph Mwakalinga", 0, "Final Interview", 6, 89, ["Python", "Django", "PostgreSQL", "Redis"], "Dar es Salaam", None),
	("Neema Kimaro", 0, "Technical Interview", 5, 83, ["Python", "Django", "MySQL"], "Morogoro", None),
	("Baraka Shirima", 0, "Shortlisted", 5, 78, ["Python", "Flask", "PostgreSQL"], "Dar es Salaam", None),
	("Fatuma Ally", 0, "AI Screening", 3, 61, ["Python", "Django"], "Mwanza", None),
	("Daniel Massawe", 0, "CV Screening", 2, 48, ["JavaScript", "Node.js"], "Dar es Salaam", None),
	("Grace Mollel", 0, "Applied", 7, 0, ["Python", "Go", "Kubernetes"], "Arusha", None),
	("Emmanuel Kileo", 0, "Rejected", 1, 32, ["PHP", "WordPress"], "Dodoma", None),

	("Sarah Nyerere", 1, "Technical Interview", 4, 91, ["React", "TypeScript", "CSS", "Figma"], "Dar es Salaam", None),
	("Peter Lyimo", 1, "Shortlisted", 3, 84, ["React", "TypeScript", "CSS"], "Dar es Salaam", None),
	("Zainab Juma", 1, "AI Screening", 3, 72, ["Vue", "JavaScript", "CSS"], "Zanzibar", None),
	("Michael Sanga", 1, "Applied", 2, 0, ["React", "JavaScript"], "Mbeya", None),
	("Rehema Mushi", 1, "Rejected", 1, 41, ["HTML", "CSS"], "Dar es Salaam", None),

	("David Katabaro", 2, "Final Interview", 6, 88, ["Product Strategy", "User Research", "SQL"], "Dar es Salaam", None),
	("Halima Mbwana", 2, "Shortlisted", 4, 80, ["Product Strategy", "User Research"], "Dar es Salaam", None),
	("Frank Ndosi", 2, "CV Screening", 3, 0, ["Project Management", "Agile"], "Arusha", None),

	("Salma Rashid", 3, "Hired", 4, 92, ["B2B Sales", "CRM", "Swahili", "Negotiation"], "Arusha", None),
	("John Temba", 3, "Offer", 3, 86, ["B2B Sales", "CRM", "Swahili"], "Arusha", None),
	("Esther Mwangi", 3, "Phone Interview", 3, 79, ["B2B Sales", "Swahili"], "Moshi", None),
	("Ibrahim Selemani", 3, "Shortlisted", 2, 74, ["Retail Sales", "CRM", "Swahili"], "Arusha", None),
	("Lucy Kessy", 3, "AI Screening", 2, 66, ["Customer Service", "Swahili"], "Mwanza", None),
	("Hamisi Bakari", 3, "Applied", 5, 0, ["B2B Sales", "Swahili", "English"], "Tanga", None),
	("Christina Urio", 3, "On Hold", 2, 58, ["Telesales", "Swahili"], "Arusha", None),
]

EMPLOYEES = [
	("Anna Mtei", "People Operations", "HR Officer", "Female"),
	("Samuel Kweka", "Engineering", "Senior Software Engineer", "Male"),
	("Ruth Mchome", "Finance", "Accountant", "Female"),
]

VERDICTS = [(90, "Strong Match"), (75, "Good Match"), (60, "Possible Match"), (0, "Weak Match")]


def _verdict(score: float) -> str:
	for floor, label in VERDICTS:
		if score >= floor:
			return label
	return "Weak Match"


def _ensure(doctype: str, name: str, payload: dict[str, Any]) -> str:
	"""Create a record if it is missing; return its name either way."""
	if frappe.db.exists(doctype, name):
		return name
	doc = frappe.get_doc({"doctype": doctype, **payload})
	doc.insert(ignore_permissions=True, ignore_if_duplicate=True)
	return doc.name


def make_demo_data() -> None:
	"""Seed the full HR + AI HR demo dataset."""
	frappe.flags.in_import = True
	random.seed(42)  # stable output across runs

	company = _setup_company()
	_setup_masters(company)
	openings = _make_openings(company)
	_make_employees(company)
	_make_candidates(openings)

	frappe.db.commit()
	_report()


# -- foundation ---------------------------------------------------------------


def _setup_company() -> str:
	if frappe.db.exists("Company", DEMO_COMPANY):
		return DEMO_COMPANY

	print(f"  creating company {DEMO_COMPANY} (this builds a chart of accounts)…")
	doc = frappe.get_doc(
		{
			"doctype": "Company",
			"company_name": DEMO_COMPANY,
			"abbr": DEMO_ABBR,
			"default_currency": "TZS",
			"country": "Tanzania",
			"domain": "Services",
			# Mandatory on Company in ERPNext v17 once a domain is set.
			"valuation_method": "FIFO",
		}
	).insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.name


def _setup_masters(company: str) -> None:
	for dept in DEPARTMENTS:
		_ensure(
			"Department",
			f"{dept} - {DEMO_ABBR}",
			{"department_name": dept, "company": company},
		)

	for designation in DESIGNATIONS:
		_ensure("Designation", designation, {"designation_name": designation})

	for branch in BRANCHES:
		_ensure("Branch", branch, {"branch": branch})

	for employment_type in EMPLOYMENT_TYPES:
		# The naming field is `employee_type_name`, not `employment_type_name`.
		_ensure(
			"Employment Type",
			employment_type,
			{"employee_type_name": employment_type},
		)

	for source in ["Website Listing", "Referral", "Campus", "LinkedIn"]:
		_ensure("Job Applicant Source", source, {"source_name": source})


def _make_employees(company: str) -> None:
	for clean, dept, designation, gender in EMPLOYEES:
		if frappe.db.exists("Employee", {"employee_name": clean}):
			continue
		try:
			frappe.get_doc(
				{
					"doctype": "Employee",
					"employee_name": clean,
					"first_name": clean.split()[0],
					"last_name": clean.split()[-1],
					"gender": gender,
					"date_of_birth": add_days(nowdate(), -365 * 32),
					"date_of_joining": add_days(nowdate(), -365 * 2),
					"company": company,
					"department": f"{dept} - {DEMO_ABBR}",
					"designation": designation,
					"status": "Active",
				}
			).insert(ignore_permissions=True)
		except Exception as exc:
			# Employee has the strictest validation of any HR doctype (holiday
			# lists, naming series). A failure here must not lose the recruitment
			# data, which is what the demo is actually for.
			print(f"  skipped employee {clean}: {str(exc)[:80]}")


# -- recruitment --------------------------------------------------------------


def _make_openings(company: str) -> list[str]:
	names = []
	for spec in OPENINGS:
		existing = frappe.db.get_value("Job Opening", {"job_title": spec["title"]}, "name")
		if existing:
			names.append(existing)
			continue

		doc = frappe.get_doc(
			{
				"doctype": "Job Opening",
				"job_title": spec["title"],
				"designation": spec["designation"],
				"company": company,
				"department": f"{spec['department']} - {DEMO_ABBR}",
				"location": spec["branch"],
				"employment_type": "Full-time",
				"status": "Open",
				# Published so the openings are visible to job seekers on /jobs.
				"publish": 1,
				"publish_applications_received": 1,
				"vacancies": spec["vacancies"],
				"description": spec["description"],
				"posted_on": add_days(nowdate(), -random.randint(10, 45)),
				"ai_min_experience": spec["min_experience"],
				"ai_education_requirement": spec["education"],
				"ai_required_skills": [
					{"skill_name": s, "importance": imp, "min_years": yrs}
					for s, imp, yrs in spec["skills"]
				],
			}
		).insert(ignore_permissions=True)
		names.append(doc.name)
	return names


def _make_candidates(openings: list[str]) -> None:
	sources = ["Website Listing", "Referral", "Campus", "LinkedIn"]

	for i, (name, opening_idx, stage, years, score, skills, location, _src) in enumerate(CANDIDATES):
		email = f"{name.split()[0].lower()}.{name.split()[-1].lower()}{DEMO_DOMAIN}"
		if frappe.db.exists("Job Applicant", {"email_id": email}):
			continue

		opening = openings[opening_idx]
		applied_days_ago = random.randint(1, 40)

		applicant = frappe.get_doc(
			{
				"doctype": "Job Applicant",
				"applicant_name": name,
				"email_id": email,
				"phone_number": f"+2557{random.randint(10, 89)}{random.randint(100000, 999999)}",
				"country": "Tanzania",
				"job_title": opening,
				"ats_stage": stage,
				"source": sources[i % len(sources)],
				"cover_letter": (
					f"I am applying for this role. I have {years} years of experience "
					f"working with {', '.join(skills[:3])}."
				),
			}
		).insert(ignore_permissions=True)

		# Backdate creation so the activity chart and "new this period" are real.
		frappe.db.set_value(
			"Job Applicant",
			applicant.name,
			"creation",
			add_days(nowdate(), -applied_days_ago),
			update_modified=False,
		)

		# Everyone past CV Screening has a parsed CV.
		if stage not in ("Applied",):
			_make_analysis(applicant.name, name, email, years, skills, location)

		# Only candidates past AI Screening carry a score.
		if score:
			_make_score(applicant.name, opening, score, skills)
			frappe.db.set_value(
				"Job Applicant", applicant.name, "ai_match_score", score, update_modified=False
			)

		# A couple of interviews, with one already evaluated.
		if stage in ("Technical Interview", "Final Interview"):
			_make_interview(applicant.name, opening, name, evaluated=stage == "Final Interview")


def _make_analysis(
	applicant: str, name: str, email: str, years: int, skills: list[str], location: str
) -> None:
	import json

	doc = frappe.get_doc(
		{
			"doctype": "AI Resume Analysis",
			"job_applicant": applicant,
			"parsing_status": "Completed",
			"content_hash": frappe.generate_hash(length=64),
			"resume_file": f"/private/files/demo_{applicant}.pdf",
			"full_name": name,
			"email_id": email,
			"phone": f"+2557{random.randint(10, 89)}{random.randint(100000, 999999)}",
			"location": location,
			"total_years_experience": years,
			"professional_summary": (
				f"{name.split()[0]} has {years} years of professional experience, "
				f"primarily working with {', '.join(skills[:3])}."
			),
			"experience_json": json.dumps(
				[
					{
						"company": random.choice(
							["Vodacom Tanzania", "NMB Bank", "Selcom", "Tigo", "Jumia"]
						),
						"job_title": "Senior Engineer" if years > 4 else "Engineer",
						"start_date": str(2026 - years),
						"end_date": "Present",
						"summary": f"Worked across {skills[0]} systems.",
					}
				],
				indent=2,
			),
			"education_json": json.dumps(
				[
					{
						"institution": random.choice(
							[
								"University of Dar es Salaam",
								"Ardhi University",
								"Nelson Mandela AIST",
								"Mzumbe University",
							]
						),
						"qualification": "BSc",
						"field_of_study": "Computer Science",
						"year": str(2026 - years - 4),
					}
				],
				indent=2,
			),
			"certifications": random.choice(["AWS Cloud Practitioner", "Scrum Master", ""]) or None,
			"languages": "English\nSwahili",
			"provider_used": "Demo Data",
			"model_used": "seeded",
			"analysis_date": add_days(nowdate(), -random.randint(1, 20)),
			"input_tokens": random.randint(1500, 4000),
			"output_tokens": random.randint(400, 900),
			"skills": [
				{"skill_name": s, "category": "Technical", "years": max(1, years - i)}
				for i, s in enumerate(skills)
			],
		}
	).insert(ignore_permissions=True)

	frappe.db.set_value(
		"Job Applicant",
		applicant,
		{"ai_resume_analysis": doc.name, "ai_parsing_status": "Completed"},
		update_modified=False,
	)


def _make_score(applicant: str, opening: str, score: int, skills: list[str]) -> None:
	required = [
		r.skill_name
		for r in frappe.get_doc("Job Opening", opening).ai_required_skills
		if r.importance == "Required"
	]
	owned = {s.lower() for s in skills}
	matched = [r for r in required if r.lower() in owned]
	missing = [r for r in required if r.lower() not in owned]

	frappe.get_doc(
		{
			"doctype": "AI Candidate Score",
			"job_applicant": applicant,
			"job_opening": opening,
			"scoring_status": "Completed",
			"source_hash": frappe.generate_hash(length=64),
			"overall_score": score,
			"skills_score": min(100, score + random.randint(-4, 6)),
			"experience_score": min(100, score + random.randint(-8, 4)),
			"education_score": random.choice([80, 90, 100]),
			"certification_score": random.choice([40, 60, 80, 100]),
			"requirements_score": min(100, score + random.randint(-5, 5)),
			"verdict": _verdict(score),
			"explanation": (
				f"Candidate evidences {len(matched)} of {len(required)} required skills. "
				f"{'Gaps remain in ' + ', '.join(missing) + '.' if missing else 'All required skills are evidenced.'}"
			),
			"matched_requirements": "\n".join(f"- {m}" for m in matched) or None,
			"missing_requirements": "\n".join(f"- {m}" for m in missing) or None,
			"recommended_action": (
				"Proceed to technical interview."
				if score >= 75
				else "Review against other applicants before progressing."
			),
			"provider_used": "Demo Data",
			"model_used": "seeded",
			"scored_on": add_days(nowdate(), -random.randint(1, 15)),
			"input_tokens": random.randint(800, 2200),
			"output_tokens": random.randint(200, 500),
		}
	).insert(ignore_permissions=True)


def _make_interview(applicant: str, opening: str, name: str, evaluated: bool) -> None:
	questions = [
		("How would you design a scalable REST API for this workload?", "Technical",
		 "Tests the depth behind the CV's framework claims.",
		 "Pagination, caching, avoiding N+1 queries."),
		("Walk me through a production incident you owned end to end.", "Behavioural",
		 "Tests ownership and follow-through.",
		 "Concrete actions, root cause, what changed afterwards."),
		("How do you decide between fixing and rewriting a legacy module?", "Situational",
		 "Tests judgement under constraints.",
		 "Weighs risk, test coverage and delivery pressure."),
		("What part of your last role would you keep, and what would you change?", "Culture",
		 "Surfaces working-style fit.", "Specific, self-aware, non-blaming."),
	]

	doc = frappe.get_doc(
		{
			"doctype": "AI Interview",
			"job_applicant": applicant,
			"job_opening": opening,
			"interview_type": "Technical",
			"status": "Evaluated" if evaluated else "Questions Generated",
			"focus_areas": "- Cloud deployment depth\n- Ownership of production systems",
			"provider_used": "Demo Data",
			"model_used": "seeded",
			"questions": [
				{"question": q, "category": c, "rationale": r, "look_for": l, "asked": int(evaluated)}
				for q, c, r, l in questions
			],
		}
	)

	if evaluated:
		doc.update(
			{
				"ratings": "Technical knowledge: 8/10, Communication: 7/10, Problem solving: 9/10",
				"interview_notes": (
					f"{name.split()[0]} answered the API design question well and reasoned "
					"clearly about trade-offs. Less confident on deployment pipelines."
				),
				"ai_summary": "Strong engineering fundamentals; cloud deployment is the main gap.",
				"strengths": "- Clear reasoning on system design\n- Strong database knowledge",
				"weaknesses": "- Limited hands-on deployment experience",
				"skills_demonstrated": "- API design\n- SQL optimisation",
				"areas_of_concern": "- Has not owned a CI/CD pipeline",
				"recommended_next_step": "Proceed to a final round focused on operational ownership.",
			}
		)

	doc.insert(ignore_permissions=True)


# -- reporting & cleanup ------------------------------------------------------


def _report() -> None:
	rows = [
		("Company", frappe.db.count("Company")),
		("Department", frappe.db.count("Department")),
		("Designation", frappe.db.count("Designation")),
		("Employee", frappe.db.count("Employee")),
		("Job Opening", frappe.db.count("Job Opening")),
		("Job Applicant", frappe.db.count("Job Applicant")),
		("AI Resume Analysis", frappe.db.count("AI Resume Analysis")),
		("AI Candidate Score", frappe.db.count("AI Candidate Score")),
		("AI Interview", frappe.db.count("AI Interview")),
	]
	print("\n  demo data seeded:")
	for label, count in rows:
		print(f"    {label:<22} {count}")


def clear_demo_data() -> None:
	"""Remove everything `make_demo_data` created.

	Applicants are matched on the demo email domain, so real records are never
	touched. The company and master data are left in place - they are usually
	shared with real work by the time anyone runs this.
	"""
	frappe.flags.in_import = True

	applicants = frappe.get_all(
		"Job Applicant", filters={"email_id": ["like", f"%{DEMO_DOMAIN}"]}, pluck="name"
	)
	for applicant in applicants:
		for doctype in ("AI Interview", "AI Candidate Score", "AI Resume Analysis"):
			for row in frappe.get_all(doctype, filters={"job_applicant": applicant}, pluck="name"):
				frappe.delete_doc(doctype, row, force=True, ignore_permissions=True)
		frappe.delete_doc("Job Applicant", applicant, force=True, ignore_permissions=True)

	for spec in OPENINGS:
		for name in frappe.get_all("Job Opening", filters={"job_title": spec["title"]}, pluck="name"):
			frappe.delete_doc("Job Opening", name, force=True, ignore_permissions=True)

	frappe.db.commit()
	print(f"  removed {len(applicants)} demo applicants and their AI records")
	print("  (company, departments and designations left in place)")
