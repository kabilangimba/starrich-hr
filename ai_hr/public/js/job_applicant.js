// Adds the AI CV-parsing action to the Job Applicant form.
//
// All AI work happens server-side (§15) - this only calls a whitelisted method
// and reflects the result. No API key or provider detail ever reaches the browser.

frappe.ui.form.on("Job Applicant", {
	refresh(frm) {
		if (frm.is_new()) return;

		if (frm.doc.resume_attachment) {
			frm.add_custom_button(
				__("Parse Resume with AI"),
				() => parse_resume(frm),
				__("AI HR")
			);
		}

		if (frm.doc.ai_resume_analysis) {
			frm.add_custom_button(
				__("View Analysis"),
				() => frappe.set_route("Form", "AI Resume Analysis", frm.doc.ai_resume_analysis),
				__("AI HR")
			);
		}

		// The parse runs in a background job, so the form listens for the result
		// instead of polling.
		frm.page.set_indicator_from_status?.();
	},

	onload(frm) {
		frappe.realtime.on("ai_hr_resume_parsed", (data) => {
			if (data.job_applicant !== frm.doc.name) return;

			if (data.status === "Completed") {
				frappe.show_alert({ message: __("Resume parsed."), indicator: "green" });
			} else if (data.status === "Failed") {
				frappe.show_alert({ message: __("Resume parsing failed."), indicator: "red" });
			}
			frm.reload_doc();
		});
	},
});

function parse_resume(frm) {
	frappe.call({
		method: "ai_hr.api.resume.parse_resume",
		args: { job_applicant: frm.doc.name },
		freeze: true,
		freeze_message: __("Reading CV…"),
		callback(r) {
			if (!r.message) return;

			const { status, message, analysis } = r.message;
			frappe.show_alert({
				message: message,
				indicator: status === "cached" ? "blue" : "orange",
			});

			// A cached result is already complete, so show it immediately.
			if (status === "cached" && analysis) {
				frappe.set_route("Form", "AI Resume Analysis", analysis);
			}
		},
	});
}
