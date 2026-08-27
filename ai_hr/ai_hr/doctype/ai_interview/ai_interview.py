# Copyright (c) 2026, Kabila Ngimba and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class AIInterview(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from ai_hr.ai_hr.doctype.ai_interview_question.ai_interview_question import AIInterviewQuestion
		from frappe.types import DF

		ai_summary: DF.SmallText | None
		areas_of_concern: DF.SmallText | None
		error_message: DF.SmallText | None
		focus_areas: DF.SmallText | None
		input_tokens: DF.Int
		interview: DF.Link | None
		interview_notes: DF.Text | None
		interview_type: DF.Literal["Phone Screen", "Technical", "Behavioural", "Final", "Panel"]
		job_applicant: DF.Link
		job_opening: DF.Link | None
		model_used: DF.Data | None
		output_tokens: DF.Int
		provider_used: DF.Data | None
		questions: DF.Table[AIInterviewQuestion]
		ratings: DF.SmallText | None
		recommended_next_step: DF.SmallText | None
		skills_demonstrated: DF.SmallText | None
		status: DF.Literal["Draft", "Questions Generated", "Evaluated", "Failed"]
		strengths: DF.SmallText | None
		weaknesses: DF.SmallText | None
	# end: auto-generated types

	_DOCTYPE_NAME = "AI Interview"
