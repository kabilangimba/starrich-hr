"""Session boot additions.

Wired through the `extend_bootinfo` hook, which runs after Frappe has assembled
`bootinfo` and before it reaches the browser.
"""

from __future__ import annotations

import frappe

#: App titles to rebrand, keyed by app name.
#:
#: hrms hard-codes "Frappe HR" in its own `add_to_apps_screen` hook, and every
#: surface that names the app - the sidebar header, the breadcrumb above a page
#: like Roster, the apps screen, the dock manager - reads `app_title` straight
#: out of `frappe.boot.app_data`. Rewriting it here relabels all of them at once,
#: without editing hrms and without a client-side patch per surface.
#:
#: Only the display label changes: `app_name` stays "hrms", so routes, hooks,
#: asset paths and `bench uninstall-app` are unaffected.
#: frappe labels itself "Framework" via its own `add_to_apps_screen` hook. That
#: name means nothing to HR staff, and the entry is where the system-level
#: settings live, so it is relabelled to match what it actually does here.
APP_TITLE_OVERRIDES = {
	"hrms": "Starrich HR",
	"frappe": "HR Settings",
}


def boot_session(bootinfo) -> None:
	for app in bootinfo.get("app_data") or []:
		new_title = APP_TITLE_OVERRIDES.get(app.get("app_name"))
		if new_title and app.get("app_title") != new_title:
			app["app_title"] = new_title
