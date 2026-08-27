// AI job description generation on the Job Opening form (§3).
//
// The draft is shown for review and only written to the record when the
// recruiter accepts it - §3 requires editing before publishing.

frappe.ui.form.on("Job Opening", {
	refresh(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button(__("Generate Description"), () => generate(frm), __("AI HR"));

		frm.add_custom_button(
			__("Score All Applicants"),
			() =>
				frappe.call({
					method: "ai_hr.api.matching.score_all_for_opening",
					args: { job_opening: frm.doc.name },
					freeze: true,
					freeze_message: __("Queueing candidates…"),
					callback: (r) =>
						r.message &&
						frappe.msgprint({
							title: __("Scoring"),
							message: r.message.message,
							indicator: "blue",
						}),
				}),
			__("AI HR")
		);

		frm.add_custom_button(
			__("Candidate Ranking"),
			() => frappe.set_route("query-report", "Candidate Ranking", { job_opening: frm.doc.name }),
			__("AI HR")
		);
	},
});

function generate(frm) {
	frappe.call({
		method: "ai_hr.api.jd.generate_job_description",
		args: { job_opening: frm.doc.name },
		freeze: true,
		freeze_message: __("Drafting job description…"),
		callback(r) {
			if (!r.message) return;
			preview(frm, r.message);
		},
	});
}

function preview(frm, result) {
	const criteria = result.sections.suggested_interview_criteria || [];

	const dialog = new frappe.ui.Dialog({
		title: __("Generated Job Description"),
		size: "large",
		fields: [
			{
				fieldname: "draft",
				fieldtype: "Text Editor",
				label: __("Draft — edit before applying"),
				default: result.html,
			},
			{
				fieldname: "criteria",
				fieldtype: "HTML",
				options: criteria.length
					? `<p><b>${__("Suggested interview criteria")}</b></p><ul>${criteria
							.map((c) => `<li>${frappe.utils.escape_html(c)}</li>`)
							.join("")}</ul>
					   <p class="text-muted">${__("Not part of the public posting.")}</p>`
					: "",
			},
		],
		primary_action_label: __("Apply to Description"),
		primary_action(values) {
			frm.set_value("description", values.draft);
			dialog.hide();
			frappe.show_alert({
				message: __("Draft applied. Review, then save."),
				indicator: "green",
			});
		},
	});

	dialog.show();
}
