"""Controller for the shadowed login page.

`login.html` in this app overrides frappe's, and Frappe resolves the controller
next to the template it picked - so without this file frappe's own `login.py`
never runs and the template loses `logo`, `for_test`, `social_login`,
`disable_signup` and everything else it needs.

All behaviour is delegated to frappe; nothing about authentication changes here.
"""

from __future__ import annotations

from frappe.www.login import get_context as _frappe_get_context

# Re-exported so any module-level flags frappe's page relies on keep working.
from frappe.www.login import *  # noqa: F401,F403


def get_context(context):
	"""Delegate to frappe's login controller."""
	return _frappe_get_context(context)
