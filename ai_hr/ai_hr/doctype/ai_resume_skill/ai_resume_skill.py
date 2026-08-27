# Copyright (c) 2026, Kabila Ngimba and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class AIResumeSkill(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		category: DF.Literal["Technical", "Soft", "Language", "Tool"]
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		skill_name: DF.Data
		years: DF.Float
	# end: auto-generated types

	_DOCTYPE_NAME = "AI Resume Skill"
