# Copyright (c) 2026, Kabila Ngimba and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class AIHRSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		api_key: DF.Password | None
		base_url: DF.Data | None
		effort: DF.Literal["", "low", "medium", "high", "xhigh", "max"]
		enable_candidate_matching: DF.Check
		enable_interview_assistant: DF.Check
		enable_jd_generation: DF.Check
		enable_resume_parsing: DF.Check
		max_tokens: DF.Int
		model: DF.Data | None
		provider: DF.Literal["Anthropic Claude", "OpenAI", "Google Gemini", "Ollama"]
		request_timeout: DF.Int
	# end: auto-generated types

	_DOCTYPE_NAME = "AI HR Settings"
