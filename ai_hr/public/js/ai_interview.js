// Interview assistant actions (§6, §7).

frappe.ui.form.on("AI Interview", {
	refresh(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button(
			frm.doc.questions?.length ? __("Regenerate Questions") : __("Generate Questions"),
			() => generate_questions(frm),
			__("AI HR")
		);

		if ((frm.doc.interview_notes || "").trim()) {
			frm.add_custom_button(__("Evaluate Interview"), () => evaluate(frm), __("AI HR"));
		}

		if (frm.doc.status === "Evaluated") {
			frm.dashboard.add_comment(
				__("AI assessment is advisory. The hiring decision is yours."),
				"blue",
				true
			);
		}
	},
});

function generate_questions(frm) {
	frappe.prompt(
		{
			fieldname: "count",
			label: __("How many questions?"),
			fieldtype: "Int",
			default: 8,
			reqd: 1,
		},
		(values) => {
			frappe.call({
				method: "ai_hr.api.interview.generate_questions",
				args: { ai_interview: frm.doc.name, count: values.count },
				freeze: true,
				freeze_message: __("Preparing questions…"),
				callback(r) {
					if (!r.message) return;
					frappe.show_alert({ message: r.message.message, indicator: "green" });
					frm.reload_doc();
				},
			});
		},
		__("Generate Questions"),
		__("Generate")
	);
}

function evaluate(frm) {
	frappe.call({
		method: "ai_hr.api.interview.evaluate_interview",
		args: { ai_interview: frm.doc.name },
		freeze: true,
		freeze_message: __("Summarising interview…"),
		callback(r) {
			if (!r.message) return;
			frappe.show_alert({ message: r.message.message, indicator: "green" });
			frm.reload_doc();
		},
	});
}
