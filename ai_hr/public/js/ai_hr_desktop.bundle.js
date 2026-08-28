// Starrich HR landing screen.
//
// Enhances Frappe's apps screen (/app/desktop) with a branded hero and a row of
// live HR summary tiles. It attaches through the `desktop_screen` event that
// frappe/desk/page/desktop/desktop.js triggers in its own setup() - no core file
// is patched, so `bench update` cannot clobber this (proposal §13, §23).
//
// Icons come from Frappe's bundled lucide sprite and type from Frappe's own font
// stack: no Tailwind, no Material Symbols, no webfont request.

frappe.provide("ai_hr.portal");

// Where the "Starrich Support" menu entry goes.
//
// Left empty it opens a ticket in the built-in help desk - ERPNext's Issue
// doctype, which is the ticket system on this bench (no Frappe Helpdesk app is
// installed). Set it to a full URL to point at an external support portal
// instead; it will then open in a new tab.
ai_hr.portal.SUPPORT_URL = "";

//: The core menu entry this replaces, matched by its built-in label.
const CORE_SUPPORT_LABEL = "Frappe Support";

$(document).on("desktop_screen", function (_event, data) {
	// Both desktop modes ("Apps" and the arrangeable "Desktop Icons") fire this
	// event and render their grid into `.desktop-container`, so the same hero and
	// tiles fit either one. Which mode is active is a site setting the admin can
	// flip at any time, so this deliberately does not branch on it.
	new ai_hr.portal.Landing(data.desktop).render();
});

ai_hr.portal.Landing = class Landing {
	constructor(desktop) {
		this.desktop = desktop;
		this.$container = $(".desktop-container");
	}

	render() {
		if (!this.$container.length) return;

		$(".sci-portal").remove(); // `make()` re-runs on every page show

		// desktop.css lays this container out as a centred flex ROW and is injected
		// with the page, i.e. after app_include_css. An equal-specificity override
		// therefore loses the cascade, so the layout rules hang off this marker
		// class instead - that extra class selector outranks the core rule
		// regardless of load order.
		this.$container.addClass("sci-stacked");

		this.$hero = $(this.hero_html()).prependTo(this.$container);
		this.$tiles = $(`<div class="sci-portal sci-tiles" role="list"></div>`).appendTo(
			this.$container
		);

		this.label_app_icons();
		this.rebrand_support_menu();
		this.skeletons();
		this.load();
	}

	// Re-caption the app tiles as "Launching <app>". Done in the DOM rather than
	// by renaming the app, because `app_title` also feeds the sidebar header, the
	// app switcher and the Desktop Icon record - renaming would change the wording
	// everywhere, not just on this screen.
	label_app_icons() {
		// The two desktop modes source their tiles differently. "Apps" mode renders
		// frappe.boot.app_data, so its titles are the authority. "Desktop Icons"
		// mode renders Desktop Icon records, whose labels are rebrandable and so
		// need not appear in app_data at all (ours reads "Starrich HR" while the
		// hook still says "Frappe HR") - there, every top-level non-folder tile is
		// something you launch.
		const icons_mode = frappe.boot.desktop_page === "Desktop Icons";
		const titles = new Set(
			(frappe.boot.app_data || []).filter((app) => app.on_apps_screen).map((app) => app.app_title)
		);

		this.$container.find(".desktop-icon").each(function () {
			const $icon = $(this);
			if ($icon.find(".folder-icon").length) return; // folders are not apps

			const $title = $icon.find(".icon-title");
			if ($title.hasClass("sci-launch-caption")) return; // never double-prefix

			const label = ($title.text() || "").trim();
			if (!label) return;
			if (!icons_mode && !titles.has(label)) return;

			$title.text(__("Launching {0}", [label])).addClass("sci-launch-caption");
		});
	}

	hero_html() {
		return `
			<section class="sci-portal sci-hero">
				<div class="sci-hero-media" aria-hidden="true"></div>
				<div class="sci-hero-inner">
					<p class="sci-hero-eyebrow"></p>
					<h1 class="sci-hero-title">${__("Welcome to Starrich HR")}</h1>
					<p class="sci-hero-sub">${__("Your people, hiring and payroll in one place.")}</p>
				</div>
			</section>
		`;
	}

	skeletons() {
		// Placeholders keep the grid from collapsing and reflowing when data lands.
		this.$tiles.html(
			Array.from({ length: 4 }, () => `<div class="sci-tile is-loading" aria-hidden="true"></div>`).join("")
		);
	}

	load() {
		frappe
			.xcall("ai_hr.api.portal.get_summary")
			.then((data) => this.paint(data))
			.catch(() => {
				// The tiles are supplementary - if the call fails the app grid below
				// is still fully usable, so fail quiet rather than alerting.
				this.$tiles.remove();
			});
	}

	paint(data) {
		if (!data) return this.$tiles.remove();

		const name = frappe.utils.escape_html(data.user || "");
		this.$hero
			.find(".sci-hero-eyebrow")
			.text(name ? `${data.greeting}, ${name}` : data.greeting || "");

		if (!data.tiles || !data.tiles.length) return this.$tiles.remove();

		this.$tiles.empty();
		data.tiles.forEach((tile) => this.$tiles.append(this.tile_html(tile)));
	}

	tile_html(tile) {
		const $el = $(`
			<a class="sci-tile" role="listitem">
				<span class="sci-tile-icon">${frappe.utils.icon(tile.icon, "md")}</span>
				<span class="sci-tile-body">
					<span class="sci-tile-label"></span>
					<span class="sci-tile-value"></span>
					<span class="sci-tile-hint"></span>
				</span>
				<span class="sci-tile-go">${frappe.utils.icon("arrow-right", "sm")}</span>
			</a>
		`);

		// Set every field as text: these strings are translated and DB-derived, so
		// they must never be interpolated as markup.
		$el.find(".sci-tile-label").text(tile.label || "");
		$el.find(".sci-tile-value").text(
			tile.value === null || tile.value === undefined ? "—" : tile.value
		);
		$el.find(".sci-tile-hint").text(tile.hint || tile.unit || "");
		$el.attr("href", tile.route || "#");
		$el.attr("aria-label", `${tile.label}: ${tile.value} ${tile.unit || ""}`.trim());
		return $el;
	}
	// Re-point the avatar menu's support entry at Starrich.
	//
	// The entry is hard-coded in frappe/desk/page/desktop/desktop.js, and its
	// `add_menu_item()` hook can only append - so rather than adding a second
	// support line, the existing item is rewritten in place. Menu.make() reads
	// `menu_items` fresh every time the menu opens, so editing the array is
	// enough and no DOM surgery is needed.
	rebrand_support_menu() {
		const swap = () => {
			// setup_avatar() builds a new menu on every page show and old ones stay
			// in frappe.menu_map, so take the newest whose parent is still on screen.
			const menus = Object.values(frappe.menu_map || {}).filter((m) => {
				const el = m && m.parent && $(m.parent)[0];
				return el && el.classList.contains("desktop-avatar") && document.body.contains(el);
			});
			const menu = menus[menus.length - 1];
			if (!menu || !Array.isArray(menu.menu_items)) return false;

			const item = menu.menu_items.find((i) => i.label === CORE_SUPPORT_LABEL);
			if (!item) return false;

			item.label = __("Starrich Support");
			item.onClick = () => ai_hr.portal.open_support();

			// "About" opens Frappe's own branding dialog (wordmark, Frappe links,
			// Frappe copyright). Hidden here the same way the navbar entry is,
			// rather than deleted, so the menu keeps its shape.
			const about = menu.menu_items.find((i) => i.label === "About");
			if (about) about.condition = () => false;

			return true;
		};

		// The desktop_screen event fires just *before* setup_avatar(), so the menu
		// does not exist yet. setup_avatar() is synchronous, so a zero-delay timeout
		// lands right after it.
		if (!swap()) window.setTimeout(swap, 0);
	}
};

// Open a support ticket. Kept off the class so the URL can be overridden from
// the console or another script without re-rendering the page.
// Drop navbar entries flagged `hidden` out of the boot payload.
//
// Frappe honours the flag in the sidebar help menu (sidebar_header.js) but the
// older navbar builder in utils.js iterates the same rows without checking it,
// so a hidden entry still renders there. Pruning the array once at boot makes
// every consumer agree, and keeps the flag itself as the single switch: clear
// `hidden` in Navbar Settings and the item comes straight back.
ai_hr.portal.prune_hidden_navbar_items = function () {
	const settings = frappe.boot && frappe.boot.navbar_settings;
	if (!settings) return;

	for (const field of ["help_dropdown", "settings_dropdown"]) {
		if (Array.isArray(settings[field])) {
			settings[field] = settings[field].filter((item) => !item.hidden);
		}
	}
};

ai_hr.portal.open_support = function () {
	const url = ai_hr.portal.SUPPORT_URL;
	if (url) {
		window.open(url, "_blank", "noopener");
		return;
	}

	// Fall back to the in-house help desk. Creating a ticket needs create rights,
	// so users without them are sent to the list rather than a permission error.
	if (frappe.model.can_create("Issue")) {
		frappe.new_doc("Issue");
	} else if (frappe.model.can_read("Issue")) {
		frappe.set_route("List", "Issue");
	} else {
		frappe.msgprint({
			title: __("Support"),
			message: __("You do not have access to the help desk. Please contact your administrator."),
			indicator: "orange",
		});
	}
};

// Re-enable legend truncation on dashboard charts.
//
// frappe/widgets/chart_widget.js builds its chart options with
// `truncateLegends: 0`, while report views, form dashboards and the charting
// library's own default all use 1. With it off, a pie legend draws every label
// at full length as SVG text - which cannot wrap - so long category names such
// as "Senior Software Engineer" or "People Operations - SIL" overlap the entry
// beside them.
//
// Turning it back on lets the library shorten labels to 18 characters, which
// keeps the charts as pie/donut rather than forcing them to bar.
(function enable_legend_truncation() {
	function patch() {
		const ChartWidget = frappe.widget && frappe.widget.widget_factory
			&& frappe.widget.widget_factory.chart;
		if (!ChartWidget || ChartWidget.prototype.__aihr_truncate_legends) return false;

		const original = ChartWidget.prototype.get_chart_args;
		ChartWidget.prototype.get_chart_args = function () {
			const args = original.apply(this, arguments);
			// Only the shapes with a cramped single-row legend need this; bar and
			// line charts put their labels on an axis and are fine as they are.
			if (["Pie", "Donut", "Percentage"].includes(this.chart_doc && this.chart_doc.type)) {
				args.truncateLegends = 1;
			}
			return args;
		};
		ChartWidget.prototype.__aihr_truncate_legends = true;
		return true;
	}

	// The desk bundle usually defines the factory before app_include_js runs, but
	// not on every route, so retry briefly rather than assume.
	if (patch()) return;
	let tries = 0;
	const timer = setInterval(() => {
		if (patch() || ++tries > 40) clearInterval(timer);
	}, 250);
})();

// Apply the navbar pruning once frappe.boot has landed. The boot payload is
// fetched by desk.js, which may run after app_include_js, so poll briefly
// rather than assume it is already there.
(function apply_navbar_pruning() {
	function prune() {
		if (!(frappe.boot && frappe.boot.navbar_settings)) return false;
		ai_hr.portal.prune_hidden_navbar_items();
		return true;
	}

	if (prune()) return;
	let tries = 0;
	const timer = setInterval(() => {
		if (prune() || ++tries > 40) clearInterval(timer);
	}, 250);
})();

// Keep the current workspace visible in the mobile bottom bar.
//
// The bar scrolls sideways and holds every workspace, so the active one is
// frequently past the right edge -- on Payroll it sat off-screen entirely, which
// left the bar giving no indication of where you actually were. Nudge it into
// view on load and on every route change.
(function keep_active_workspace_visible() {
	const MOBILE = "(max-width: 767.98px)";

	function reveal() {
		if (!window.matchMedia || !window.matchMedia(MOBILE).matches) return;

		const strip = document.querySelector(".workspace-dock .workspace-dock-items");
		const active = strip && strip.querySelector(".workspace-dock-item.active");
		if (!strip || !active) return;

		// Deliberately not scrollIntoView(): that scrolls the *page* vertically as
		// well, yanking the user away from what they were reading. Only the strip
		// should move.
		const centred = active.offsetLeft - (strip.clientWidth - active.offsetWidth) / 2;
		const max = strip.scrollWidth - strip.clientWidth;
		// Clamped, so an item near either end settles flush instead of being left
		// half-clipped against the edge.
		const target = Math.max(0, Math.min(centred, max));

		// Instant, not smooth: on first paint the animation had not finished before
		// the page was usable, which left the active workspace clipped at the edge
		// -- exactly the confusion this is meant to remove.
		strip.scrollLeft = target;
	}

	// The dock repaints its active item slightly after the route settles.
	function schedule() {
		window.setTimeout(reveal, 150);
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", schedule);
	} else {
		schedule();
	}

	// frappe.router may not exist yet when app_include_js runs; retry briefly
	// rather than assume, matching the other patches in this file.
	let tries = 0;
	const timer = setInterval(() => {
		if (window.frappe && frappe.router && frappe.router.on) {
			frappe.router.on("change", schedule);
			clearInterval(timer);
		} else if (++tries > 40) {
			clearInterval(timer);
		}
	}, 250);
})();
