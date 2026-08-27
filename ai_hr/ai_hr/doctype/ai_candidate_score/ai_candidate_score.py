# Copyright (c) 2026, Kabila Ngimba and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class AICandidateScore(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		certification_score: DF.Percent
		education_score: DF.Percent
		error_message: DF.SmallText | None
		experience_score: DF.Percent
		explanation: DF.SmallText | None
		input_tokens: DF.Int
		job_applicant: DF.Link
		job_opening: DF.Link
		matched_requirements: DF.SmallText | None
		missing_requirements: DF.SmallText | None
		model_used: DF.Data | None
		output_tokens: DF.Int
		overall_score: DF.Percent
		provider_used: DF.Data | None
		recommended_action: DF.SmallText | None
		requirements_score: DF.Percent
		scored_on: DF.Datetime | None
		scoring_status: DF.Literal["Queued", "Processing", "Completed", "Failed"]
		skills_score: DF.Percent
		source_hash: DF.Data | None
		verdict: DF.Literal["", "Strong Match", "Good Match", "Possible Match", "Weak Match"]
	# end: auto-generated types

	_DOCTYPE_NAME = "AI Candidate Score"
