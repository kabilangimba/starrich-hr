// Filters for the AI Skill Gap Analysis report.
frappe.query_reports["AI Skill Gap Analysis"] = {
	filters: [
		{
			fieldname: "job_opening",
			label: __("Job Opening"),
			fieldtype: "Link",
			options: "Job Opening",
			// Optional: left blank the report covers every scored opening.
		},
	],
};
