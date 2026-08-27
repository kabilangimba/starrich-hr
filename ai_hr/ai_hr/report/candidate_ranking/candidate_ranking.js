// Filters for the Candidate Ranking report (§5).
frappe.query_reports["Candidate Ranking"] = {
	filters: [
		{
			fieldname: "job_opening",
			label: __("Job Opening"),
			fieldtype: "Link",
			options: "Job Opening",
			reqd: 1,
		},
		{
			fieldname: "verdict",
			label: __("Verdict"),
			fieldtype: "Select",
			options: ["", "Strong Match", "Good Match", "Possible Match", "Weak Match"],
		},
		{
			fieldname: "minimum_score",
			label: __("Minimum Score"),
			fieldtype: "Int",
			default: 0,
		},
	],

	formatter(value, row, column, data, default_formatter) {
		const formatted = default_formatter(value, row, column, data);

		// Colour the headline score so a recruiter can scan the list at a glance.
		if (column.fieldname === "overall_score" && data) {
			const score = data.overall_score || 0;
			const colour = score >= 90 ? "green" : score >= 75 ? "blue" : score >= 60 ? "orange" : "gray";
			return `<span style="color: var(--text-on-${colour}, inherit); font-weight: 600">${formatted}</span>`;
		}
		return formatted;
	},
};
