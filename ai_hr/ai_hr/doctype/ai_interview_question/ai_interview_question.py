# Copyright (c) 2026, Kabila Ngimba and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class AIInterviewQuestion(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		asked: DF.Check
		category: DF.Literal["Technical", "Behavioural", "Situational", "Experience", "Culture"]
		look_for: DF.SmallText | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		question: DF.SmallText
		rationale: DF.SmallText | None
	# end: auto-generated types

	_DOCTYPE_NAME = "AI Interview Question"
