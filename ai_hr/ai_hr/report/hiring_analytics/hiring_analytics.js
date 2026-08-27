frappe.query_reports["Hiring Analytics"] = {
	filters: [
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: ["", "Open", "Closed"].join("\n"),
		},
	],
};
