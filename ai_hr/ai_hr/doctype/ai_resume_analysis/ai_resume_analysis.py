# Copyright (c) 2026, Kabila Ngimba and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class AIResumeAnalysis(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from ai_hr.ai_hr.doctype.ai_resume_skill.ai_resume_skill import AIResumeSkill
		from frappe.types import DF

		analysis_date: DF.Datetime | None
		certifications: DF.SmallText | None
		content_hash: DF.Data | None
		education_json: DF.Code | None
		email_id: DF.Data | None
		error_message: DF.SmallText | None
		experience_json: DF.Code | None
		full_name: DF.Data | None
		github_url: DF.Data | None
		input_tokens: DF.Int
		job_applicant: DF.Link
		languages: DF.SmallText | None
		linkedin_url: DF.Data | None
		location: DF.Data | None
		model_used: DF.Data | None
		output_tokens: DF.Int
		parsing_status: DF.Literal["Queued", "Processing", "Completed", "Failed"]
		phone: DF.Data | None
		portfolio_url: DF.Data | None
		professional_summary: DF.SmallText | None
		projects: DF.SmallText | None
		provider_used: DF.Data | None
		resume_file: DF.Data | None
		skills: DF.Table[AIResumeSkill]
		total_years_experience: DF.Float
	# end: auto-generated types

	_DOCTYPE_NAME = "AI Resume Analysis"
