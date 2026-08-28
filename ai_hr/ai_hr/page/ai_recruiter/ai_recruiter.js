// Recruiter assistant chat page (§8).
//
// Thin client: it posts the question and renders the answer. All retrieval and
// permission checking happens server-side in ai_hr.api.assistant.
//
// The page is deliberately dark while the rest of the Desk keeps the user's
// theme: every rule is scoped under `.airc-page`, a class added to this page's
// wrapper only, so nothing leaks into other pages.

frappe.pages["ai-recruiter"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("AI Recruiter Assistant"),
		single_column: true,
	});

	$(wrapper).addClass("airc-page");
	inject_styles();
	new RecruiterChat(page).render();
};

const SUGGESTIONS = () => [
	__("Show me the top 10 candidates for Senior Backend Engineer"),
	__("Which candidates have more than 3 years of Python experience?"),
	__("Who is missing the required AWS certification?"),
	__("Compare the top two candidates for Frontend Engineer"),
];

class RecruiterChat {
	constructor(page) {
		this.page = page;
		this.$body = $(page.body);
		this.turns = 0;
	}

	render() {
		this.$body.html(`
			<div class="airc">
				<div class="airc-scroll">
					<div class="airc-thread"></div>
				</div>
				<div class="airc-composer">
					<div class="airc-suggestions"></div>
					<form class="airc-inputrow" autocomplete="off">
						<textarea class="airc-input" rows="1"
							placeholder="${__("Ask about candidates or openings…")}"></textarea>
						<button type="submit" class="airc-send" aria-label="${__("Send")}">
							${frappe.utils.icon("send", "sm")}
						</button>
					</form>
					<p class="airc-disclaimer">
						${__("Answers come from your HR records and are advisory. Hiring decisions are yours.")}
					</p>
				</div>
			</div>
		`);

		this.$thread = this.$body.find(".airc-thread");
		this.$scroll = this.$body.find(".airc-scroll");
		this.$input = this.$body.find(".airc-input");

		this.empty_state();
		this.suggestions();
		this.bind();
		this.$input.trigger("focus");
	}

	bind() {
		this.$body.on("submit", ".airc-inputrow", (e) => {
			e.preventDefault();
			this.ask(this.$input.val());
		});

		// Enter sends, Shift+Enter makes a new line - the convention every chat
		// UI uses, and the reason the input is a textarea rather than an <input>.
		this.$body.on("keydown", ".airc-input", (e) => {
			if (e.key === "Enter" && !e.shiftKey) {
				e.preventDefault();
				this.ask(this.$input.val());
			}
		});

		this.$body.on("input", ".airc-input", (e) => this.autosize(e.currentTarget));
		this.$body.on("click", ".airc-chip", (e) => this.ask($(e.currentTarget).text().trim()));
	}

	// Grow the composer with the text, up to a cap so it never eats the thread.
	autosize(el) {
		el.style.height = "auto";
		el.style.height = Math.min(el.scrollHeight, 160) + "px";
	}

	empty_state() {
		this.$thread.html(`
			<div class="airc-empty">
				<div class="airc-empty-badge">${frappe.utils.icon("sparkles", "lg")}</div>
				<h3>${__("Ask about your candidates")}</h3>
				<p>${__("I answer from the applicants, scores and openings already in your HR records.")}</p>
			</div>
		`);
	}

	suggestions() {
		this.$body
			.find(".airc-suggestions")
			.html(
				SUGGESTIONS()
					.map(
						(s) =>
							`<button type="button" class="airc-chip">${frappe.utils.escape_html(s)}</button>`
					)
					.join("")
			);
	}

	bubble(role, text, meta = "", variant = "") {
		if (!this.turns) this.$thread.empty();
		this.turns += 1;

		const avatar =
			role === "user"
				? `<div class="airc-avatar is-user">${frappe.get_abbr(
						frappe.session.user_fullname || "U"
				  )}</div>`
				: `<div class="airc-avatar is-bot">${frappe.utils.icon("sparkles", "sm")}</div>`;

		const $row = $(`
			<div class="airc-turn is-${role} ${variant}">
				${avatar}
				<div class="airc-bubble">
					<div class="airc-text"></div>
					${meta ? `<div class="airc-meta">${frappe.utils.escape_html(meta)}</div>` : ""}
				</div>
			</div>
		`);

		const $text = $row.find(".airc-text");
		if (role === "assistant" && !variant) {
			// The model replies in markdown, so "**bold**" has to be rendered
			// rather than shown literally. frappe.markdown() runs showdown and
			// then whitelist-sanitizes the result (see utils/tools.js), which is
			// what makes this safe for model output: a prompt injection carried
			// in a CV cannot smuggle markup through it.
			$text.addClass("airc-md").html(frappe.markdown(normalize_markdown(text || "")));
		} else {
			// User text and error strings are shown verbatim, never parsed.
			$text.text(text);
		}

		this.$thread.append($row);
		this.scroll_down();
		return $row;
	}

	pending() {
		if (!this.turns) this.$thread.empty();
		const $row = $(`
			<div class="airc-turn is-assistant">
				<div class="airc-avatar is-bot">${frappe.utils.icon("sparkles", "sm")}</div>
				<div class="airc-bubble airc-typing">
					<span></span><span></span><span></span>
				</div>
			</div>
		`);
		this.$thread.append($row);
		this.scroll_down();
		return $row;
	}

	scroll_down() {
		this.$scroll.stop().animate({ scrollTop: this.$scroll[0].scrollHeight }, 200);
	}

	ask(question) {
		question = (question || "").trim();
		if (!question || this.busy) return;

		this.busy = true;
		this.bubble("user", question);
		this.$input.val("");
		this.autosize(this.$input[0]);
		this.$body.find(".airc-suggestions").addClass("is-hidden");

		const $pending = this.pending();
		const done = () => {
			$pending.remove();
			this.busy = false;
			this.$input.trigger("focus");
		};

		frappe.call({
			method: "ai_hr.api.assistant.ask",
			args: { question },
			error: (r) => {
				done();
				this.bubble("assistant", extract_error(r), __("Not answered"), "is-error");
			},
			callback: (r) => {
				done();
				if (!r.message) {
					this.bubble("assistant", __("No response was returned."), __("Not answered"), "is-error");
					return;
				}
				const { answer, rows, model } = r.message;
				const meta = rows
					? __("From {0} record(s){1}", [rows, model ? ` · ${model}` : ""])
					: __("No matching records");
				this.bubble("assistant", answer, meta);
			},
		});
	}
}

// Snap indented list markers onto 4-space steps before handing the text to
// showdown.
//
// Models indent nested bullets by three spaces, which showdown does not read as
// nesting: it closes the outer <ol> and opens a new one, so every numbered item
// renders as "1.". Only lines that already begin with a list marker are touched,
// so indented code blocks and ordinary paragraphs are left exactly as they are.
function normalize_markdown(md) {
	return String(md).replace(/^([ \t]+)([-*+]|\d+\.)([ \t])/gm, (match, indent, marker, space) => {
		const width = indent.replace(/\t/g, "    ").length;
		const depth = Math.max(1, Math.round(width / 3));
		return " ".repeat(depth * 4) + marker + space;
	});
}

// Pull a readable message out of a Frappe error response. The shape differs by
// failure path, so check each before falling back.
function extract_error(r) {
	const raw =
		r?._server_messages ||
		r?.responseJSON?._server_messages ||
		(() => {
			try {
				return JSON.parse(r?.responseText || "null")?._server_messages;
			} catch (e) {
				return null;
			}
		})();

	if (raw) {
		try {
			const parsed = (typeof raw === "string" ? JSON.parse(raw) : raw).map((m) => {
				try {
					const obj = typeof m === "string" ? JSON.parse(m) : m;
					return obj.message || obj;
				} catch (e) {
					return m;
				}
			});
			const text = parsed.join("\n").replace(/<[^>]+>/g, "");
			if (text.trim()) return text;
		} catch (e) {
			/* fall through */
		}
	}
	return __("The assistant could not answer. Check the provider settings in AI HR Settings.");
}

function inject_styles() {
	if (document.getElementById("airc-styles")) return;

	// Colours come from Frappe's own theme variables, so this page follows the
	// Desk appearance the user has chosen - light or dark - instead of forcing
	// its own. Every rule is still scoped under `.airc-page`, the class this page
	// adds to its own wrapper, so the layout cannot affect other pages.
	const css = `
.airc-page .airc {
	display: flex; flex-direction: column;
	height: calc(100vh - var(--navbar-height, 60px) - 110px);
	/* dvh tracks the viewport as a mobile browser's URL bar collapses; vh does
	 * not, and the difference is the composer sitting below the fold until you
	 * scroll. Declared second so browsers without dvh keep the vh line. */
	height: calc(100dvh - var(--navbar-height, 60px) - 110px);
	max-width: 820px; margin: 0 auto;
}

.airc-page .airc-scroll { flex: 1 1 auto; overflow-y: auto; padding: 1rem .25rem 1.25rem; }
.airc-page .airc-thread { display: flex; flex-direction: column; gap: 1.6rem; }

/* -- empty state -- */
.airc-page .airc-empty { text-align: center; padding: 3.5rem 1rem; color: var(--text-muted); }
.airc-page .airc-empty-badge {
	width: 54px; height: 54px; margin: 0 auto 1rem;
	display: grid; place-items: center; border-radius: 16px;
	background: var(--bg-light-gray); color: var(--text-color);
}
.airc-page .airc-empty h3 { font-size: 1.1rem; margin: 0 0 .4rem; color: var(--text-color); }
.airc-page .airc-empty p { font-size: .875rem; margin: 0 auto; max-width: 430px; }

/* -- turns -- */
.airc-page .airc-turn { display: flex; gap: .75rem; align-items: flex-start; }
.airc-page .airc-turn.is-user { flex-direction: row-reverse; }

.airc-page .airc-avatar {
	flex: 0 0 28px; width: 28px; height: 28px; border-radius: 8px;
	display: grid; place-items: center; font-size: .68rem; font-weight: 600;
	margin-top: 2px;
}
.airc-page .airc-avatar.is-user { background: var(--bg-blue); color: var(--text-on-blue, #1657c9); }
.airc-page .airc-avatar.is-bot { background: var(--bg-light-gray); color: var(--text-color); }

/* The assistant reads as a document, not a speech bubble - the convention in
 * ChatGPT and Claude, and it gives long structured answers room to breathe. */
.airc-page .airc-turn.is-assistant .airc-bubble {
	background: none; border: 0; padding: 0; max-width: 100%;
}
.airc-page .airc-turn.is-user .airc-bubble {
	background: var(--bg-blue); color: var(--text-color);
	border-radius: 14px 4px 14px 14px; padding: .6rem .85rem; max-width: 78%;
}
.airc-page .airc-turn.is-error .airc-bubble {
	background: var(--bg-red, #fdf0ef); border: 1px solid var(--red-300, #f5b8b3);
	border-radius: 12px; padding: .65rem .85rem;
}
.airc-page .airc-bubble {
	line-height: 1.62; font-size: .9rem;
	/* Long model output and pasted IDs must wrap, never widen the page. */
	overflow-wrap: anywhere;
}
.airc-page .airc-text { white-space: pre-wrap; }
/* Markdown output brings its own block spacing, so the pre-wrap used for plain
 * text would double every gap. */
.airc-page .airc-text.airc-md { white-space: normal; }
.airc-page .airc-meta { margin-top: .5rem; font-size: .7rem; color: var(--text-muted); }

/* -- rendered markdown -- */
.airc-page .airc-md > :first-child { margin-top: 0; }
.airc-page .airc-md > :last-child { margin-bottom: 0; }
.airc-page .airc-md p { margin: 0 0 .75rem; }
.airc-page .airc-md strong { font-weight: 600; color: var(--heading-color, var(--text-color)); }
.airc-page .airc-md em { font-style: italic; }
.airc-page .airc-md h1,
.airc-page .airc-md h2,
.airc-page .airc-md h3 {
	font-size: .95rem; font-weight: 600; color: var(--heading-color, var(--text-color));
	margin: 1.1rem 0 .5rem; line-height: 1.4;
}
.airc-page .airc-md ul,
.airc-page .airc-md ol { margin: 0 0 .75rem; padding-left: 1.25rem; }
.airc-page .airc-md li { margin: .3rem 0; }
/* showdown wraps an <li> that has nested content in a <p>; without this the
 * list gains a blank line before every sub-list. */
.airc-page .airc-md li > p { margin: 0 0 .25rem; }
.airc-page .airc-md li::marker { color: var(--text-muted); }
.airc-page .airc-md ul ul,
.airc-page .airc-md ol ul,
.airc-page .airc-md ul ol { margin: .3rem 0 .1rem; }
.airc-page .airc-md code {
	background: var(--bg-light-gray); border: 1px solid var(--border-color);
	border-radius: 5px; padding: .1em .38em; font-size: .84em;
}
.airc-page .airc-md pre {
	background: var(--bg-light-gray); border: 1px solid var(--border-color);
	border-radius: 10px; padding: .8rem .9rem; overflow-x: auto; margin: 0 0 .75rem;
}
.airc-page .airc-md pre code { background: none; border: 0; padding: 0; }
.airc-page .airc-md a { color: var(--primary, #2a78d6); }
.airc-page .airc-md blockquote {
	margin: 0 0 .75rem; padding: .1rem 0 .1rem .85rem;
	border-left: 2px solid var(--border-color); color: var(--text-muted);
}
.airc-page .airc-md hr { border: 0; border-top: 1px solid var(--border-color); margin: 1rem 0; }
/* Tables can be wider than the thread; scroll them, never the page. */
.airc-page .airc-md table {
	width: 100%; border-collapse: collapse; margin: 0 0 .75rem; font-size: .85em;
	display: block; overflow-x: auto;
}
.airc-page .airc-md th,
.airc-page .airc-md td { border: 1px solid var(--border-color); padding: .4rem .55rem; text-align: left; }
.airc-page .airc-md th { background: var(--bg-light-gray); font-weight: 600; }

/* -- typing indicator -- */
.airc-page .airc-typing { display: inline-flex; gap: 5px; align-items: center; padding: .5rem 0; }
.airc-page .airc-typing span {
	width: 6px; height: 6px; border-radius: 50%;
	background: var(--text-muted); opacity: .45;
	animation: airc-blink 1.3s infinite ease-in-out;
}
.airc-page .airc-typing span:nth-child(2) { animation-delay: .18s; }
.airc-page .airc-typing span:nth-child(3) { animation-delay: .36s; }
@keyframes airc-blink { 0%,80%,100% { opacity:.25; transform: translateY(0);} 40% { opacity:.9; transform: translateY(-3px);} }
@media (prefers-reduced-motion: reduce) { .airc-page .airc-typing span { animation: none; opacity: .5; } }

/* -- composer -- */
.airc-page .airc-composer { flex: 0 0 auto; padding: .35rem 0 0; }
.airc-page .airc-suggestions { display: flex; flex-wrap: wrap; gap: .45rem; margin-bottom: .65rem; }
.airc-page .airc-suggestions.is-hidden { display: none; }
.airc-page .airc-chip {
	border: 1px solid var(--border-color); background: var(--card-bg, var(--fg-color));
	color: var(--text-muted);
	border-radius: 999px; padding: .35rem .8rem; font-size: .78rem;
	cursor: pointer; transition: color .12s ease, border-color .12s ease;
}
.airc-page .airc-chip:hover { color: var(--text-color); border-color: var(--text-muted); }

.airc-page .airc-inputrow {
	display: flex; gap: .5rem; align-items: flex-end;
	background: var(--card-bg, var(--fg-color));
	border: 1px solid var(--border-color);
	border-radius: 16px; padding: .45rem .45rem .45rem 1rem;
	transition: border-color .12s ease, box-shadow .12s ease;
}
.airc-page .airc-inputrow:focus-within {
	border-color: var(--primary, #2a78d6);
	box-shadow: 0 0 0 3px var(--bg-blue, rgba(42,120,214,.15));
}
.airc-page .airc-input {
	flex: 1 1 auto; border: 0; background: transparent; outline: none; resize: none;
	font-size: .9rem; line-height: 1.5; color: var(--text-color);
	padding: .4rem 0; min-width: 0; max-height: 160px; font-family: inherit;
}
.airc-page .airc-input::placeholder { color: var(--text-muted); }
.airc-page .airc-send {
	flex: 0 0 auto; width: 34px; height: 34px; border: 0; border-radius: 10px;
	background: var(--primary, #2a78d6); color: #fff;
	display: grid; place-items: center; cursor: pointer;
	transition: opacity .12s ease;
}
.airc-page .airc-send:hover { opacity: .88; }
.airc-page .airc-send svg { fill: none; stroke: currentColor; }
.airc-page .airc-disclaimer {
	margin: .6rem 0 0; font-size: .72rem; color: var(--text-muted); text-align: center;
}

@media (max-width: 640px) {
	.airc-page .airc-turn.is-user .airc-bubble { max-width: 88%; }
	.airc-page .airc { height: calc(100vh - 168px); }
	.airc-page .airc { height: calc(100dvh - 168px); }

	.airc-page .airc-scroll { padding: .75rem .25rem 1rem; }
	.airc-page .airc-thread { gap: 1.25rem; }

	/* The empty state was ~3.5rem of padding on a screen that has none to give. */
	.airc-page .airc-empty { padding: 2rem .5rem; }
	.airc-page .airc-empty-badge { width: 46px; height: 46px; margin-bottom: .75rem; }

	/* Four chips wrapped to three rows and pushed the composer off-screen. One
	 * row that scrolls sideways instead; the negative margin lets it bleed to
	 * the screen edge so it reads as scrollable. */
	.airc-page .airc-suggestions {
		flex-wrap: nowrap;
		overflow-x: auto;
		-webkit-overflow-scrolling: touch;
		scrollbar-width: none;
		margin: 0 -.25rem .55rem;
		padding: 0 .25rem .15rem;
	}
	.airc-page .airc-suggestions::-webkit-scrollbar { display: none; }
	/* Capped so the next chip always peeks in at the edge - otherwise the first
	 * suggestion fills the row and the strip looks like a single button rather
	 * than something you can swipe. Tapping still sends the full text. */
	.airc-page .airc-chip {
		flex: 0 0 auto;
		max-width: 85%;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	/* 16px exactly: iOS Safari zooms the whole page when a focused field is
	 * under 16px, and the user is then left panned sideways mid-conversation. */
	.airc-page .airc-input { font-size: 16px; }
	.airc-page .airc-inputrow { padding: .4rem .4rem .4rem .85rem; }
	/* 40px clears the 44px-ish touch-target floor once padding is counted. */
	.airc-page .airc-send { width: 40px; height: 40px; }

	.airc-page .airc-disclaimer { font-size: .68rem; margin-top: .45rem; }
}
`;
	$("<style>").attr("id", "airc-styles").text(css).appendTo(document.head);
}
