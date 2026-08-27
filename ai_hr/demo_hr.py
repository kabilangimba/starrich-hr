"""Training demo data across every Frappe HR module.

`ai_hr.demo` seeds the recruitment/AI side. This module fills the rest - leaves,
attendance, payroll, expenses, performance, tax & benefits and employee lifecycle
- so a training session has something to look at in every part of the app.

Design notes:

* **Idempotent.** Everything goes through `_ensure`, which skips a record that
  already exists. Re-running tops up gaps rather than duplicating.
* **Section-isolated.** Each section runs in its own try/except and reports its
  own outcome. One module failing (a missing account, a version difference)
  must not stop the rest from seeding.
* **Traceable.** Records carry the demo company, so `clear_demo_hr_data()` can
  find them again.
"""

from __future__ import annotations

import random
from typing import Any

import frappe
from frappe.utils import add_days, add_months, flt, getdate, nowdate

COMPANY = "Starrich International"
ABBR = "SIL"
DOMAIN = "@demo.aihr.test"

# Deterministic, so a re-run produces the same figures.
RNG = random.Random(20260827)

_report: list[str] = []


def _log(section: str, msg: str) -> None:
	_report.append(f"  {section:<22} {msg}")


def _ensure(doctype: str, filters: dict[str, Any], payload: dict[str, Any],
            submit: bool = False) -> str | None:
	"""Create a document unless one matching `filters` already exists."""
	existing = frappe.db.get_value(doctype, filters, "name")
	if existing:
		return existing
	try:
		doc = frappe.get_doc({"doctype": doctype, **payload})
		doc.insert(ignore_permissions=True, ignore_mandatory=False)
		if submit and doc.meta.is_submittable:
			doc.submit()
		return doc.name
	except Exception as exc:
		_log(doctype, f"skipped: {str(exc)[:110]}")
		return None


# -- foundation ---------------------------------------------------------------

GRADES = [
	("G1 - Associate", 900_000),
	("G2 - Officer", 1_400_000),
	("G3 - Senior", 2_200_000),
	("G4 - Lead", 3_200_000),
	("G5 - Manager", 4_500_000),
]

LEAVE_TYPES = [
	# (name, allocation, is_lwp, carry_forward)
	("Annual Leave", 28, 0, 1),
	("Sick Leave", 14, 0, 0),
	("Casual Leave", 7, 0, 0),
	("Maternity Leave", 84, 0, 0),
	("Leave Without Pay", 0, 1, 0),
]


def seed_foundation() -> None:
	year = getdate(nowdate()).year

	# Many HR reports declare `default: frappe.defaults.get_user_default("Company")`
	# on a required company filter. With no default set, those reports open with
	# "Please select company." and their dashboard charts render empty - which is
	# what happened to the Attendance Count chart.
	#
	# The doc has to be *saved*: Global Defaults' on_update writes the
	# DefaultValue rows that get_user_default() reads. Setting the field with
	# db.set_value updates the Single but leaves those rows missing.
	if frappe.db.exists("Company", COMPANY):
		gd = frappe.get_single("Global Defaults")
		if gd.default_company != COMPANY:
			gd.default_company = COMPANY
			gd.save(ignore_permissions=True)
			frappe.clear_cache()
		_log("Global Defaults", f"default company = {COMPANY}")

	for grade, base in GRADES:
		_ensure("Employee Grade", {"name": grade}, {"__newname": grade, "default_base_pay": base})
	_log("Employee Grade", f"{frappe.db.count('Employee Grade')} total")

	# Holiday list: weekends plus a few public holidays.
	hl_name = f"{COMPANY} Holidays {year}"
	if not frappe.db.exists("Holiday List", hl_name):
		hl = frappe.get_doc({
			"doctype": "Holiday List",
			"holiday_list_name": hl_name,
			"from_date": f"{year}-01-01",
			"to_date": f"{year}-12-31",
		})
		for label, date in [("New Year's Day", f"{year}-01-01"),
		                    ("Union Day", f"{year}-04-26"),
		                    ("Workers' Day", f"{year}-05-01"),
		                    ("Independence Day", f"{year}-12-09"),
		                    ("Christmas Day", f"{year}-12-25")]:
			hl.append("holidays", {"description": label, "holiday_date": date})
		# `weekly_off` is required before insert; without it validation fails with
		# "Please select weekly off day".
		hl.weekly_off = "Sunday"
		try:
			hl.insert(ignore_permissions=True)
		except Exception as exc:
			_log("Holiday List", f"skipped: {str(exc)[:110]}")
	_log("Holiday List", f"{frappe.db.count('Holiday List')} total")

	for name, alloc, lwp, carry in LEAVE_TYPES:
		# autoname is `field:leave_type_name`, so __newname is ignored here.
		_ensure("Leave Type", {"name": name}, {
			"leave_type_name": name,
			"max_leaves_allowed": alloc,
			"is_lwp": lwp,
			"is_carry_forward": carry,
			"include_holiday": 0,
		})
	_log("Leave Type", f"{frappe.db.count('Leave Type')} total")

	_ensure("Leave Period", {"company": COMPANY, "from_date": f"{year}-01-01"}, {
		"from_date": f"{year}-01-01", "to_date": f"{year}-12-31",
		"company": COMPANY, "is_active": 1,
	})
	_log("Leave Period", f"{frappe.db.count('Leave Period')} total")

	for t in ["Travel", "Meals", "Accommodation", "Office Supplies", "Training", "Medical"]:
		# autoname is `field:expense_type`.
		_ensure("Expense Claim Type", {"name": t}, {"expense_type": t})
	_log("Expense Claim Type", f"{frappe.db.count('Expense Claim Type')} total")

	for shift, start, end in [("General", "08:00:00", "17:00:00"),
	                          ("Morning", "06:00:00", "14:00:00"),
	                          ("Evening", "14:00:00", "22:00:00")]:
		_ensure("Shift Type", {"name": shift}, {
			"__newname": shift, "start_time": start, "end_time": end,
			"enable_auto_attendance": 0,
		})
	_log("Shift Type", f"{frappe.db.count('Shift Type')} total")

	# autoname is Prompt, so the name must be supplied explicitly.
	_ensure("Payroll Period", {"company": COMPANY, "start_date": f"{year}-01-01"}, {
		"__newname": f"{year} Payroll Period",
		"company": COMPANY, "start_date": f"{year}-01-01", "end_date": f"{year}-12-31",
	})
	_log("Payroll Period", f"{frappe.db.count('Payroll Period')} total")


# -- people -------------------------------------------------------------------

STAFF = [
	# (first, last, gender, designation, department, grade, branch, joined)
	("Neema", "Shirima", "Female", "HR Manager", "People Operations", "G5 - Manager", "Dar es Salaam", "2021-03-15"),
	("Baraka", "Mushi", "Male", "Senior Software Engineer", "Engineering", "G4 - Lead", "Dar es Salaam", "2021-07-01"),
	("Amina", "Juma", "Female", "Software Engineer", "Engineering", "G3 - Senior", "Dar es Salaam", "2022-01-10"),
	("Joseph", "Massawe", "Male", "Software Engineer", "Engineering", "G2 - Officer", "Mwanza", "2023-02-06"),
	("Grace", "Mollel", "Female", "Product Manager", "Product", "G4 - Lead", "Arusha", "2022-05-23"),
	("Daniel", "Kimaro", "Male", "Sales Executive", "Sales", "G3 - Senior", "Arusha", "2022-09-12"),
	("Fatuma", "Said", "Female", "Sales Executive", "Sales", "G2 - Officer", "Dar es Salaam", "2023-06-05"),
	("Peter", "Ngowi", "Male", "Accountant", "Finance", "G3 - Senior", "Dar es Salaam", "2021-11-08"),
	("Rehema", "Chuwa", "Female", "Finance Officer", "Finance", "G2 - Officer", "Mwanza", "2023-08-21"),
	("Elias", "Mwakalinga", "Male", "IT Support", "Engineering", "G1 - Associate", "Dar es Salaam", "2024-01-15"),
	("Zawadi", "Lyimo", "Female", "Marketing Officer", "Marketing", "G2 - Officer", "Arusha", "2023-04-03"),
	("Hamisi", "Ally", "Male", "Operations Officer", "Operations", "G2 - Officer", "Mwanza", "2024-03-11"),
]

#: Joiners dated inside the current month, so the Tenure workspace's
#: "New Hires (This Month)" quick list has something to list. Their join date is
#: filled in at seed time rather than hard-coded, so this keeps working later.
RECENT_HIRES = [
	("Salma", "Mbwana", "Female", "Software Engineer", "Engineering", "G2 - Officer", "Dar es Salaam"),
	("Emmanuel", "Kessy", "Male", "Sales Executive", "Sales", "G2 - Officer", "Arusha"),
]


def _dept(name: str) -> str | None:
	"""Departments are company-scoped, e.g. 'Engineering - SIL'."""
	full = f"{name} - {ABBR}"
	if frappe.db.exists("Department", full):
		return full
	return frappe.db.get_value("Department", {"department_name": name}, "name")


def seed_employees() -> None:
	holiday_list = frappe.db.get_value("Holiday List", {}, "name")

	# v17 does not read Employee.holiday_list or Company.default_holiday_list for
	# this: hrms.utils.holiday_list.get_assigned_holiday_list() looks up a
	# submitted "Holiday List Assignment". Without one, Leave Application refuses
	# every request with "No Holiday List was found". One company-wide assignment
	# covers every employee.
	if holiday_list:
		frappe.db.set_value("Company", COMPANY, "default_holiday_list", holiday_list)
		if not frappe.db.exists("Holiday List Assignment",
		                        {"assigned_to": COMPANY, "docstatus": 1}):
			_ensure("Holiday List Assignment", {"assigned_to": COMPANY}, {
				"applicable_for": "Company",
				"assigned_to": COMPANY,
				"holiday_list": holiday_list,
				"from_date": f"{getdate(nowdate()).year}-01-01",
			}, submit=True)

	for first, last, gender, desig, dept, grade, branch, joined in STAFF:
		if frappe.db.exists("Employee", {"employee_name": f"{first} {last}"}):
			continue
		payload = {
			"first_name": first,
			"last_name": last,
			"employee_name": f"{first} {last}",
			"gender": gender,
			"date_of_birth": add_years_str(joined, -28),
			"date_of_joining": joined,
			"company": COMPANY,
			"status": "Active",
			"designation": desig if frappe.db.exists("Designation", desig) else None,
			"department": _dept(dept),
			"branch": branch if frappe.db.exists("Branch", branch) else None,
			"grade": grade if frappe.db.exists("Employee Grade", grade) else None,
			"employment_type": "Full-time" if frappe.db.exists("Employment Type", "Full-time") else None,
			"holiday_list": holiday_list,
			"personal_email": f"{first.lower()}.{last.lower()}{DOMAIN}",
		}
		_ensure("Employee", {"employee_name": f"{first} {last}"}, payload)

	# Hires dated within the current month.
	first_of_month = getdate(nowdate()).replace(day=1)
	for i, (first, last, gender, desig, dept, grade, branch) in enumerate(RECENT_HIRES):
		joined = add_days(first_of_month, 2 + i * 3)
		if getdate(joined) > getdate(nowdate()):
			joined = nowdate()
		if frappe.db.exists("Employee", {"employee_name": f"{first} {last}"}):
			continue
		_ensure("Employee", {"employee_name": f"{first} {last}"}, {
			"first_name": first, "last_name": last,
			"employee_name": f"{first} {last}",
			"gender": gender,
			"date_of_birth": add_years_str(str(first_of_month), -26),
			"date_of_joining": joined,
			"company": COMPANY, "status": "Active",
			"designation": desig if frappe.db.exists("Designation", desig) else None,
			"department": _dept(dept),
			"branch": branch if frappe.db.exists("Branch", branch) else None,
			"grade": grade if frappe.db.exists("Employee Grade", grade) else None,
			"employment_type": "Full-time",
			"holiday_list": holiday_list,
			"personal_email": f"{first.lower()}.{last.lower()}{DOMAIN}",
		})

	_log("Employee", f"{frappe.db.count('Employee')} total")


def add_years_str(date_str: str, years: int) -> str:
	d = getdate(date_str)
	return str(d.replace(year=d.year + years))


def _employees(limit: int | None = None) -> list[dict]:
	rows = frappe.get_all(
		"Employee",
		filters={"status": "Active", "company": COMPANY},
		fields=["name", "employee_name", "department", "designation", "date_of_joining", "grade"],
		order_by="date_of_joining",
	)
	return rows[:limit] if limit else rows


# -- leaves -------------------------------------------------------------------


def seed_leaves() -> None:
	year = getdate(nowdate()).year
	period = frappe.db.get_value("Leave Period", {"company": COMPANY}, "name")
	staff = _employees()
	if not staff:
		_log("Leaves", "no employees to allocate to")
		return

	allocated = applied = 0
	for emp in staff:
		for lt, days in (("Annual Leave", 28), ("Sick Leave", 14)):
			if not frappe.db.exists("Leave Type", lt):
				continue
			if frappe.db.exists("Leave Allocation",
			                    {"employee": emp.name, "leave_type": lt, "docstatus": 1}):
				continue
			name = _ensure("Leave Allocation",
				{"employee": emp.name, "leave_type": lt, "from_date": f"{year}-01-01"},
				{
					"employee": emp.name, "leave_type": lt,
					"from_date": f"{year}-01-01", "to_date": f"{year}-12-31",
					"new_leaves_allocated": days, "company": COMPANY,
					"leave_period": period,
				}, submit=True)
			if name:
				allocated += 1

	# Leave Approver is mandatory on Leave Application, so pick a real HR user.
	approver = _leave_approver()

	# A spread of applications: approved, pending and one rejected.
	states = ["Approved", "Approved", "Open", "Approved", "Rejected", "Open"]
	for i, emp in enumerate(staff[:6]):
		# Kept older than the attendance window: attendance is already marked for
		# recent weekdays, and Leave Application rejects overlapping dates.
		start = add_days(nowdate(), -RNG.randint(35, 120))
		end = add_days(start, RNG.randint(0, 2))
		state = states[i % len(states)]
		name = _ensure("Leave Application",
			{"employee": emp.name, "from_date": start},
			{
				"employee": emp.name, "leave_type": "Annual Leave",
				"from_date": start, "to_date": end,
				"company": COMPANY, "status": state,
				"leave_approver": approver,
				"description": "Demo leave request for training.",
			}, submit=state == "Approved")
		if name:
			applied += 1

	# The Leaves dashboard has a "Employees on Leave (This Month)" card, which
	# stays at zero if every application sits in an earlier month.
	from calendar import monthrange

	for offset, emp in enumerate(staff[6:9], start=2):
		# A few days ahead: attendance is already marked for recent weekdays, and
		# Leave Application refuses to overlap it. Clamped to the current month so
		# the "this month" card still counts it.
		today = getdate(nowdate())
		last_day = monthrange(today.year, today.month)[1]
		start = today.replace(day=min(today.day + offset, last_day))
		if frappe.db.exists("Leave Application", {"employee": emp.name, "from_date": start}):
			continue
		if _ensure("Leave Application", {"employee": emp.name, "from_date": start}, {
			"employee": emp.name, "leave_type": "Annual Leave",
			"from_date": start, "to_date": start,
			"company": COMPANY, "status": "Approved",
			"leave_approver": approver,
			"description": "Demo leave in the current month.",
		}, submit=True):
			applied += 1

	_log("Leave Allocation", f"{frappe.db.count('Leave Allocation')} total (+{allocated})")
	_log("Leave Application", f"{frappe.db.count('Leave Application')} total (+{applied})")


# -- shift & attendance -------------------------------------------------------


def _leave_approver() -> str | None:
	"""A user who can approve leave: an HR Manager if there is one."""
	for role in ("HR Manager", "HR User"):
		rows = frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"},
		                      pluck="parent", limit_page_length=20)
		for u in rows:
			if u not in ("Administrator", "Guest") and frappe.db.get_value("User", u, "enabled"):
				return u
	return "Administrator"


def seed_attendance(days_back: int = 21) -> None:
	staff = _employees()
	if not staff:
		_log("Attendance", "no employees")
		return

	shifts = frappe.get_all("Shift Type", pluck="name")
	for i, emp in enumerate(staff):
		if shifts and not frappe.db.exists("Shift Assignment", {"employee": emp.name, "docstatus": 1}):
			_ensure("Shift Assignment", {"employee": emp.name},
				{
					"employee": emp.name, "company": COMPANY,
					"shift_type": shifts[i % len(shifts)],
					"start_date": add_days(nowdate(), -90), "status": "Active",
				}, submit=True)

	made = 0
	for emp in staff:
		for back in range(1, days_back + 1):
			day = add_days(nowdate(), -back)
			if getdate(day).weekday() >= 5:      # weekend
				continue
			if frappe.db.exists("Attendance", {"employee": emp.name, "attendance_date": day,
			                                   "docstatus": ["<", 2]}):
				continue
			roll = RNG.random()
			status = "Present" if roll < 0.88 else ("Half Day" if roll < 0.94 else "On Leave")
			# `shift` matters: the Shift Attendance report keys off it, and without
			# it every attendance row is invisible to that report.
			if _ensure("Attendance", {"employee": emp.name, "attendance_date": day},
				{
					"employee": emp.name, "attendance_date": day, "status": status,
					"company": COMPANY,
					"shift": frappe.db.get_value(
						"Shift Assignment", {"employee": emp.name, "docstatus": 1}, "shift_type"),
				}, submit=True):
				made += 1

	_log("Shift Assignment", f"{frappe.db.count('Shift Assignment')} total")
	_log("Attendance", f"{frappe.db.count('Attendance')} total (+{made})")


# -- expenses -----------------------------------------------------------------


def _company_account(*account_types: str) -> str | None:
	"""Find a usable company account, trying each type in turn."""
	for at in account_types:
		name = frappe.db.get_value(
			"Account", {"company": COMPANY, "account_type": at, "is_group": 0}, "name")
		if name:
			return name
	return None


def seed_expenses() -> None:
	staff = _employees()
	types = frappe.get_all("Expense Claim Type", pluck="name")
	if not (staff and types):
		_log("Expenses", "missing employees or claim types")
		return

	payable = _company_account("Payable")
	expense_acc = _company_account("Expense Account", "Cost of Goods Sold", "Expenses Included In Valuation")
	# Required by Expense Claim's on_submit; without it the claim can be saved but
	# never submitted, and a naive submit-then-commit leaves it marked submitted
	# with no accounting entries behind it.
	cost_center = frappe.db.get_value("Cost Center", {"company": COMPANY, "is_group": 0}, "name")

	claims = 0
	samples = [("Travel", 185_000, "Client visit to Arusha"),
	           ("Meals", 45_000, "Team lunch after sprint review"),
	           ("Accommodation", 260_000, "Two nights, Mwanza branch"),
	           ("Office Supplies", 78_000, "Stationery and printer toner"),
	           ("Training", 450_000, "Advanced Excel workshop"),
	           ("Medical", 120_000, "Annual health check")]

	for i, (etype, amount, why) in enumerate(samples):
		emp = staff[i % len(staff)]
		if etype not in types:
			continue
		if frappe.db.exists("Expense Claim", {"employee": emp.name, "remark": why}):
			continue
		payload = {
			"employee": emp.name,
			"company": COMPANY,
			# Both are required; without exchange_rate the insert fails with a
			# bare "exchange_rate" mandatory error.
			"currency": frappe.db.get_value("Company", COMPANY, "default_currency") or "TZS",
			"exchange_rate": 1,
			"posting_date": add_days(nowdate(), -RNG.randint(3, 45)),
			"remark": why,
			"approval_status": ["Approved", "Draft", "Approved", "Rejected", "Approved", "Draft"][i % 6],
			"expenses": [{
				"expense_date": add_days(nowdate(), -RNG.randint(5, 50)),
				"expense_type": etype,
				"description": why,
				"amount": amount,
				"sanctioned_amount": amount,
				"cost_center": cost_center,
			}],
		}
		if payable:
			payload["payable_account"] = payable
		if expense_acc:
			payload["expenses"][0]["default_account"] = expense_acc
		if _ensure("Expense Claim", {"employee": emp.name, "remark": why}, payload):
			claims += 1

	# Employee Advance validates that the account is of type "Employee Advance".
	# The stock chart of accounts has none, so create one under the payable group.
	# Employee Advance insists the account is of type *Receivable* - despite the
	# field being called advance_account and an "Employee Advance" account type
	# existing. Reuse an existing receivable, or create one under its parent.
	advance_acc = None
	receivable = _company_account("Receivable")
	if receivable:
		existing = frappe.db.get_value("Account",
			{"account_name": "Employee Advances", "company": COMPANY}, "name")
		advance_acc = existing or _ensure("Account",
			{"account_name": "Employee Advances", "company": COMPANY}, {
				"account_name": "Employee Advances", "company": COMPANY,
				"parent_account": frappe.db.get_value("Account", receivable, "parent_account"),
				"account_type": "Receivable", "root_type": "Asset", "is_group": 0,
			}) or receivable

	# Purpose of Travel is a link target, not free text.
	for purpose in ("Client meeting", "Conference", "Site inspection"):
		_ensure("Purpose of Travel", {"name": purpose}, {"__newname": purpose,
		                                                 "purpose_of_travel": purpose})

	for i, emp in enumerate(staff[:4]):
		_ensure("Employee Advance", {"employee": emp.name, "purpose": "Field work advance"}, {
			"employee": emp.name, "company": COMPANY,
			"purpose": "Field work advance",
			"advance_amount": [200_000, 350_000, 150_000, 400_000][i],
			"posting_date": add_days(nowdate(), -RNG.randint(5, 40)),
			"advance_account": advance_acc,
		})

	for i, emp in enumerate(staff[:3]):
		_ensure("Travel Request", {"employee": emp.name, "purpose_of_travel": "Client meeting"}, {
			"employee": emp.name, "company": COMPANY,
			"purpose_of_travel": "Client meeting",
			"travel_type": "Domestic",
			"travel_funding": "Require Full Funding",
		})

	_log("Expense Claim", f"{frappe.db.count('Expense Claim')} total (+{claims})")
	_log("Employee Advance", f"{frappe.db.count('Employee Advance')} total")
	_log("Travel Request", f"{frappe.db.count('Travel Request')} total")


# -- payroll ------------------------------------------------------------------


def seed_payroll() -> None:
	staff = _employees()
	if not staff:
		_log("Payroll", "no employees")
		return

	# Components: earnings and deductions the structure needs.
	for name, ctype, abbr in [("Basic", "Earning", "B"),
	                          ("House Rent Allowance", "Earning", "HRA"),
	                          ("Transport Allowance", "Earning", "TA"),
	                          ("Income Tax", "Deduction", "IT"),
	                          ("Pension (NSSF)", "Deduction", "NSSF")]:
		_ensure("Salary Component", {"salary_component": name}, {
			"salary_component": name, "type": ctype, "salary_component_abbr": abbr,
		})

	structure = "Starrich Standard Salary"
	if not frappe.db.exists("Salary Structure", structure):
		doc = frappe.get_doc({
			"doctype": "Salary Structure",
			"__newname": structure,
			"company": COMPANY,
			"currency": frappe.db.get_value("Company", COMPANY, "default_currency") or "TZS",
			"payroll_frequency": "Monthly",
			"earnings": [
				{"salary_component": "Basic", "amount_based_on_formula": 1, "formula": "base * 0.6"},
				{"salary_component": "House Rent Allowance", "amount_based_on_formula": 1, "formula": "base * 0.25"},
				{"salary_component": "Transport Allowance", "amount": 150_000},
			],
			"deductions": [
				{"salary_component": "Pension (NSSF)", "amount_based_on_formula": 1, "formula": "base * 0.10"},
				{"salary_component": "Income Tax", "amount_based_on_formula": 1, "formula": "base * 0.08"},
			],
		})
		try:
			doc.insert(ignore_permissions=True)
			doc.submit()
		except Exception as exc:
			_log("Salary Structure", f"skipped: {str(exc)[:120]}")
	_log("Salary Structure", f"{frappe.db.count('Salary Structure')} total")

	if not frappe.db.exists("Salary Structure", structure):
		return

	assigned = 0
	for emp in staff:
		base = flt(frappe.db.get_value("Employee Grade", emp.grade, "default_base_pay")) or 1_200_000
		if frappe.db.exists("Salary Structure Assignment",
		                    {"employee": emp.name, "docstatus": 1}):
			continue
		# Income Tax Computation only considers assignments that carry a tax slab;
		# without it the report aborts with "No employees found with selected
		# filters and active salary structure".
		slab = frappe.db.get_value("Income Tax Slab",
			{"company": COMPANY, "docstatus": 1}, "name")

		if _ensure("Salary Structure Assignment",
			{"employee": emp.name, "salary_structure": structure},
			{
				"employee": emp.name, "salary_structure": structure,
				"from_date": add_months(nowdate(), -6),
				"company": COMPANY, "base": base,
				"income_tax_slab": slab,
			}, submit=True):
			assigned += 1
	_log("Salary Structure Assignment", f"{frappe.db.count('Salary Structure Assignment')} total (+{assigned})")

	slips = 0
	for emp in staff[:8]:
		start = getdate(add_months(nowdate(), -1)).replace(day=1)
		if frappe.db.exists("Salary Slip", {"employee": emp.name, "start_date": start}):
			continue
		if _ensure("Salary Slip", {"employee": emp.name, "start_date": start}, {
			"employee": emp.name, "company": COMPANY,
			"salary_structure": structure, "start_date": start,
			"payroll_frequency": "Monthly",
		}, submit=True):
			slips += 1
	_log("Salary Slip", f"{frappe.db.count('Salary Slip')} total (+{slips})")


# -- performance --------------------------------------------------------------


def seed_performance() -> None:
	staff = _employees()
	if not staff:
		_log("Performance", "no employees")
		return

	# `key_result_area` links to the KRA doctype, so the KRAs must exist first.
	kras = [("Delivery quality", 40), ("Collaboration", 30), ("Initiative", 30)]
	for kra, _w in kras:
		_ensure("KRA", {"name": kra}, {"title": kra})   # autoname: field:title

	template = "Standard Appraisal"
	# autoname is `field:template_title`, so __newname alone is not enough.
	_ensure("Appraisal Template", {"name": template}, {
		"template_title": template,
		"description": "Standard KRA template used for demo appraisals.",
		"goals": [{"key_result_area": kra, "per_weightage": w} for kra, w in kras],
	})

	cycle = f"FY{getdate(nowdate()).year} Review"
	_ensure("Appraisal Cycle", {"cycle_name": cycle}, {
		"cycle_name": cycle, "company": COMPANY,
		"start_date": add_months(nowdate(), -6), "end_date": nowdate(),
		"kra_evaluation_method": "Manual Rating",
	})
	_log("Appraisal Cycle", f"{frappe.db.count('Appraisal Cycle')} total")

	made = 0
	for emp in staff[:8]:
		if frappe.db.exists("Appraisal", {"employee": emp.name, "appraisal_cycle": cycle}):
			continue
		if _ensure("Appraisal", {"employee": emp.name, "appraisal_cycle": cycle}, {
			"employee": emp.name, "company": COMPANY,
			"appraisal_cycle": cycle, "appraisal_template": template,
		}):
			made += 1
	_log("Appraisal", f"{frappe.db.count('Appraisal')} total (+{made})")

	goals = [("Ship the candidate portal", "Product"),
	         ("Reduce time-to-hire by 20%", "People Operations"),
	         ("Close Q3 sales target", "Sales"),
	         ("Complete tax filing on time", "Finance")]
	for i, (subject, _dept_name) in enumerate(goals):
		emp = staff[i % len(staff)]
		_ensure("Goal", {"goal_name": subject}, {
			"goal_name": subject, "employee": emp.name,
			"start_date": add_months(nowdate(), -3), "end_date": add_months(nowdate(), 3),
			"status": ["In Progress", "Completed", "In Progress", "Pending"][i % 4],
			"progress": [55, 100, 40, 0][i % 4],
		})
	_log("Goal", f"{frappe.db.count('Goal')} total")


# -- recruitment extras -------------------------------------------------------


def seed_recruitment_extras() -> None:
	openings = frappe.get_all("Job Opening", filters={"company": COMPANY},
	                          fields=["name", "job_title", "designation"], limit_page_length=10)
	applicants = frappe.get_all("Job Applicant", fields=["name", "applicant_name", "job_title"],
	                            limit_page_length=40)
	if not (openings and applicants):
		_log("Recruitment", "no openings or applicants")
		return

	# Staffing plan for the year.
	year = getdate(nowdate()).year
	plan = _ensure("Staffing Plan", {"company": COMPANY, "name": f"{year} Hiring Plan"}, {
		"__newname": f"{year} Hiring Plan",
		"company": COMPANY,
		"from_date": f"{year}-01-01", "to_date": f"{year}-12-31",
		"staffing_details": [
			{"designation": o.designation, "vacancies": 2, "estimated_cost_per_position": 24_000_000}
			for o in openings if o.designation
		][:4],
	})
	_log("Staffing Plan", f"{frappe.db.count('Staffing Plan')} total")

	offers = interviews = 0
	for i, app in enumerate(applicants[:6]):
		opening = next((o for o in openings if o.name == app.job_title), openings[0])

		if not frappe.db.exists("Job Offer", {"job_applicant": app.name}):
			if _ensure("Job Offer", {"job_applicant": app.name}, {
				"job_applicant": app.name,
				"company": COMPANY,
				"status": ["Accepted", "Awaiting Response", "Accepted", "Rejected",
				           "Awaiting Response", "Accepted"][i % 6],
				"offer_date": add_days(nowdate(), -RNG.randint(3, 40)),
				"designation": opening.designation,
				"job_applicant_name": app.applicant_name,
			}):
				offers += 1

		if frappe.db.exists("DocType", "Interview") and not frappe.db.exists(
				"Interview", {"job_applicant": app.name}):
			# `skill` links to the Skill doctype, so those masters come first.
			for sk in ("Problem Solving", "Communication"):
				if frappe.db.exists("DocType", "Skill"):
					_ensure("Skill", {"name": sk}, {"__newname": sk, "skill_name": sk})
			round_name = _ensure("Interview Type", {"name": "Technical Round"}, {
				"interview_type_name": "Technical Round",     # autoname: field:...
				"expected_skill_set": [{"skill": "Problem Solving"},
				                       {"skill": "Communication"}],
			}) if frappe.db.exists("DocType", "Interview Type") else None
			payload = {
				"job_applicant": app.name,
				"scheduled_on": add_days(nowdate(), RNG.randint(-15, 10)),
				"from_time": "10:00:00", "to_time": "11:00:00",
				"status": ["Cleared", "Pending", "Cleared", "Rejected", "Pending", "Cleared"][i % 6],
			}
			if round_name:
				payload["interview_type"] = round_name
			if _ensure("Interview", {"job_applicant": app.name}, payload):
				interviews += 1

	_log("Job Offer", f"{frappe.db.count('Job Offer')} total (+{offers})")
	if frappe.db.exists("DocType", "Interview"):
		_log("Interview", f"{frappe.db.count('Interview')} total (+{interviews})")


# -- employee lifecycle -------------------------------------------------------


def seed_lifecycle() -> None:
	staff = _employees()
	if len(staff) < 4:
		_log("Lifecycle", "not enough employees")
		return

	# Employee Onboarding is a *pre-hire* flow keyed on the applicant and their
	# offer, not on an existing employee, so drive it from the accepted offers.
	offers = frappe.get_all("Job Offer", filters={"status": "Accepted"},
	                        fields=["name", "job_applicant", "designation"],
	                        limit_page_length=2)
	for offer in offers:
		if frappe.db.exists("Employee Onboarding", {"job_offer": offer.name}):
			continue
		_ensure("Employee Onboarding", {"job_offer": offer.name}, {
			"job_applicant": offer.job_applicant,
			"job_offer": offer.name,
			"employee_name": frappe.db.get_value("Job Applicant", offer.job_applicant,
			                                     "applicant_name") or "New Joiner",
			"company": COMPANY,
			"designation": offer.designation,
			"boarding_status": "In Process",
			"boarding_begins_on": add_days(nowdate(), 7),
			"date_of_joining": add_days(nowdate(), 14),
			"activities": [
				{"activity_name": "Issue laptop and access badge", "role": "HR Manager"},
				{"activity_name": "Payroll and bank details", "role": "HR Manager"},
				{"activity_name": "Team introduction", "role": "HR Manager"},
			],
		})

	# One promotion, one transfer.
	promo = staff[2]
	_ensure("Employee Promotion", {"employee": promo.name}, {
		"employee": promo.name, "company": COMPANY,
		"promotion_date": add_days(nowdate(), -30),
		"promotion_details": [{
			"property": "Designation", "current": promo.designation,
			"new": "Senior Software Engineer", "fieldname": "designation",
		}],
	})

	move = staff[3]
	_ensure("Employee Transfer", {"employee": move.name}, {
		"employee": move.name, "company": COMPANY,
		"transfer_date": add_days(nowdate(), -20),
		"transfer_details": [{
			"property": "Branch", "current": "Dar es Salaam",
			"new": "Arusha", "fieldname": "branch",
		}],
	})

	# One separation, in process.
	leaver = staff[-1]
	_ensure("Employee Separation", {"employee": leaver.name}, {
		"employee": leaver.name, "company": COMPANY,
		"boarding_status": "In Process",
		"boarding_begins_on": add_days(nowdate(), -5),
		"resignation_letter_date": add_days(nowdate(), -10),
		"activities": [
			{"activity_name": "Exit interview", "role": "HR Manager"},
			{"activity_name": "Return company assets", "role": "HR Manager"},
		],
	})

	for dt in ("Employee Onboarding", "Employee Promotion", "Employee Transfer", "Employee Separation"):
		_log(dt, f"{frappe.db.count(dt)} total")


# -- tax & benefits -----------------------------------------------------------


def seed_tax_benefits() -> None:
	year = getdate(nowdate()).year
	currency = frappe.db.get_value("Company", COMPANY, "default_currency") or "TZS"

	slab = f"Tanzania PAYE {year}"
	_ensure("Income Tax Slab", {"name": slab}, {
		"__newname": slab,
		"company": COMPANY, "currency": currency,
		"effective_from": f"{year}-01-01",
		"slabs": [
			{"from_amount": 0, "to_amount": 270_000, "percent_deduction": 0},
			{"from_amount": 270_001, "to_amount": 520_000, "percent_deduction": 8},
			{"from_amount": 520_001, "to_amount": 760_000, "percent_deduction": 20},
			{"from_amount": 760_001, "to_amount": 1_000_000, "percent_deduction": 25},
			{"from_amount": 1_000_001, "to_amount": 0, "percent_deduction": 30},
		],
	}, submit=True)
	_log("Income Tax Slab", f"{frappe.db.count('Income Tax Slab')} total")

	period = frappe.db.get_value("Payroll Period", {"company": COMPANY}, "name")

	# Neither category nor sub-category ships with HRMS, so seed one of each.
	category = frappe.db.get_value("Employee Tax Exemption Category", {}, "name") or _ensure(
		"Employee Tax Exemption Category", {"name": "Insurance Premium"},
		{"__newname": "Insurance Premium", "max_amount": 1_000_000})
	sub = frappe.db.get_value("Employee Tax Exemption Sub Category", {}, "name") or _ensure(
		"Employee Tax Exemption Sub Category", {"name": "Life Insurance"},
		{"__newname": "Life Insurance", "exemption_category": category,
		 "max_amount": 500_000, "is_active": 1})
	if not (period and sub):
		_log("Tax Exemption", "no payroll period or exemption categories configured")
		return

	made = 0
	for emp in _employees()[:5]:
		if frappe.db.exists("Employee Tax Exemption Declaration",
		                    {"employee": emp.name, "payroll_period": period}):
			continue
		if _ensure("Employee Tax Exemption Declaration",
			{"employee": emp.name, "payroll_period": period},
			{
				"employee": emp.name, "company": COMPANY,
				"payroll_period": period, "currency": currency,
				"declarations": [{
					"exemption_sub_category": sub,
					"exemption_category": category,
					"amount": 250_000,
				}],
			}, submit=True):
			made += 1
	_log("Tax Exemption Declaration",
	     f"{frappe.db.count('Employee Tax Exemption Declaration')} total (+{made})")


# -- orchestration ------------------------------------------------------------


SECTIONS = [
	("Foundation", "seed_foundation"),
	("Employees", "seed_employees"),
	("Leaves", "seed_leaves"),
	("Attendance", "seed_attendance"),
	("Expenses", "seed_expenses"),
	("Payroll", "seed_payroll"),
	("Performance", "seed_performance"),
	("Recruitment", "seed_recruitment_extras"),
	("Lifecycle", "seed_lifecycle"),
	("Tax & Benefits", "seed_tax_benefits"),
]


def seed_all() -> str:
	"""Seed every module. Safe to re-run; each section is isolated."""
	_report.clear()
	for label, fn_name in SECTIONS:
		_report.append(f"\n  --- {label} ---")
		try:
			globals()[fn_name]()
			frappe.db.commit()
		except Exception as exc:
			frappe.db.rollback()
			_log(label, f"section failed: {str(exc)[:120]}")
	return "\n".join(_report)


# -- tenure: grievance, skills, training --------------------------------------


def seed_tenure_extras() -> None:
	staff = _employees()
	if len(staff) < 5:
		_log("Tenure", "not enough employees")
		return

	for gt in ("Workplace Conduct", "Compensation", "Working Conditions", "Harassment"):
		_ensure("Grievance Type", {"name": gt}, {"__newname": gt,
		                                         "description": f"{gt} related grievance."})
	_log("Grievance Type", f"{frappe.db.count('Grievance Type')} total")

	# Grievances: raised by one employee against another.
	cases = [
		("Shift roster changed without notice", "Working Conditions", "Open"),
		("Overtime hours not reflected in payslip", "Compensation", "Investigated"),
		("Disagreement over task allocation", "Workplace Conduct", "Resolved"),
	]
	for i, (subject, gtype, status) in enumerate(cases):
		raiser, against = staff[i], staff[(i + 4) % len(staff)]
		_ensure("Employee Grievance", {"subject": subject}, {
			"subject": subject,
			"raised_by": raiser.name,
			"date": add_days(nowdate(), -RNG.randint(5, 45)),
			"status": status,
			"grievance_against_party": "Employee",
			"grievance_against": against.name,
			"grievance_type": gtype,
			"description": f"Demo grievance for training: {subject}.",
			"associated_document_type": None,
		})
	_log("Employee Grievance", f"{frappe.db.count('Employee Grievance')} total")

	# Skill maps - one per employee, with a rating per skill.
	SKILLS = {
		"Engineering": ["Python", "JavaScript", "SQL", "Problem Solving"],
		"Sales": ["Negotiation", "CRM", "Communication"],
		"Finance": ["Accounting", "Excel", "Reporting"],
		"People Operations": ["Recruitment", "Communication", "Employee Relations"],
	}
	made = 0
	for emp in staff[:8]:
		if frappe.db.exists("Employee Skill Map", {"employee": emp.name}):
			continue
		dept = (emp.department or "").split(" - ")[0]
		skills = SKILLS.get(dept, ["Communication", "Problem Solving", "Teamwork"])
		for sk in skills:
			_ensure("Skill", {"name": sk}, {"__newname": sk, "skill_name": sk})
		if _ensure("Employee Skill Map", {"employee": emp.name}, {
			"employee": emp.name,
			"employee_name": emp.employee_name,
			"designation": emp.designation,
			"employee_skills": [
				{"skill": sk, "proficiency": RNG.choice(["Beginner", "Intermediate", "Expert"])}
				for sk in skills
			],
		}):
			made += 1
	_log("Employee Skill Map", f"{frappe.db.count('Employee Skill Map')} total (+{made})")

	# Training programme -> event -> attendance -> feedback / result.
	programs = [
		("Onboarding Essentials", "Company policies, tools and ways of working."),
		("Advanced Excel for Finance", "Pivot tables, modelling and reporting."),
		("Effective Interviewing", "Structured interviewing and fair assessment."),
	]
	for name, desc in programs:
		_ensure("Training Program", {"name": name}, {
			"training_program": name, "company": COMPANY, "description": desc,
		})
	_log("Training Program", f"{frappe.db.count('Training Program')} total")

	events = [
		("Onboarding Essentials - Aug", "Onboarding Essentials", "Dar es Salaam", -14, "Completed"),
		("Advanced Excel - Sept", "Advanced Excel for Finance", "Mwanza", 10, "Scheduled"),
		# Inside the current week, for the "Trainings (This Week)" quick list -
		# the other two fall outside it.
		("Effective Interviewing - This Week", "Effective Interviewing",
		 "Dar es Salaam", 1, "Scheduled"),
	]
	for ev_name, program, location, offset, status in events:
		start = f"{add_days(nowdate(), offset)} 09:00:00"
		end = f"{add_days(nowdate(), offset)} 16:00:00"
		attendees = [{"employee": e.name, "employee_name": e.employee_name,
		              "department": e.department} for e in staff[:6]]
		_ensure("Training Event", {"name": ev_name}, {
			"event_name": ev_name,
			"training_program": program,
			"event_status": status,
			"type": "Workshop",
			"location": location,
			"start_time": start,
			"end_time": end,
			"introduction": f"Demo training event: {program}.",
			"company": COMPANY,
			"employees": attendees,
		}, submit=True)
	_log("Training Event", f"{frappe.db.count('Training Event')} total")

	# Feedback and results only make sense for the completed event.
	done = frappe.db.get_value("Training Event", {"event_status": "Completed"}, "name")
	if not done:
		_log("Training Feedback", "no completed event")
		return

	fb = res = 0
	for emp in staff[:4]:
		if not frappe.db.exists("Training Feedback", {"employee": emp.name, "training_event": done}):
			if _ensure("Training Feedback", {"employee": emp.name, "training_event": done}, {
				"employee": emp.name, "employee_name": emp.employee_name,
				"training_event": done,
				"feedback": RNG.choice([
					"Clear and well paced; the hands-on section was the most useful part.",
					"Good content. Would have liked more time for questions.",
					"Very relevant to my day-to-day work.",
				]),
			}, submit=True):
				fb += 1

	if not frappe.db.exists("Training Result", {"training_event": done}):
		if _ensure("Training Result", {"training_event": done}, {
			"training_event": done,
			"employees": [{
				"employee": e.name, "employee_name": e.employee_name,
				"hours": 6, "grade": RNG.choice(["A", "B", "A"]),
				"comments": "Completed all exercises.",
			} for e in staff[:4]],
		}, submit=True):
			res += 1

	_log("Training Feedback", f"{frappe.db.count('Training Feedback')} total (+{fb})")
	_log("Training Result", f"{frappe.db.count('Training Result')} total (+{res})")


# -- remaining masters --------------------------------------------------------


def seed_masters() -> None:
	"""The Reports & Masters items that the module-level seeders do not cover."""
	staff = _employees()
	if not staff:
		_log("Masters", "no employees")
		return

	for g in ("Field Staff", "Head Office", "Interns", "Management"):
		_ensure("Employee Group", {"name": g}, {"employee_group_name": g})
	_log("Employee Group", f"{frappe.db.count('Employee Group')} total")

	# Leave policy, then assign it to everyone.
	policy = frappe.db.get_value("Leave Policy", {"title": "Standard Leave Policy"}, "name")
	if not policy:
		policy = _ensure("Leave Policy", {"title": "Standard Leave Policy"}, {
			"title": "Standard Leave Policy",
			"leave_policy_details": [
				{"leave_type": lt, "annual_allocation": days}
				for lt, days in (("Annual Leave", 28), ("Sick Leave", 14), ("Casual Leave", 7))
				if frappe.db.exists("Leave Type", lt)
			],
		}, submit=True)
	_log("Leave Policy", f"{frappe.db.count('Leave Policy')} total")

	period = frappe.db.get_value("Leave Period", {"company": COMPANY}, "name")
	if policy and period:
		pr = frappe.db.get_value("Leave Period", period, ["from_date", "to_date"], as_dict=True)
		for emp in staff[:6]:
			if frappe.db.exists("Leave Policy Assignment", {"employee": emp.name, "docstatus": 1}):
				continue
			_ensure("Leave Policy Assignment", {"employee": emp.name, "leave_policy": policy}, {
				"employee": emp.name, "leave_policy": policy, "company": COMPANY,
				"assignment_based_on": "Leave Period", "leave_period": period,
				"effective_from": pr.from_date, "effective_to": pr.to_date,
			}, submit=True)
		_log("Leave Policy Assignment", f"{frappe.db.count('Leave Policy Assignment')} total")

	# Check-ins: an IN and an OUT per employee for the last few working days.
	made = 0
	for emp in staff[:8]:
		for back in range(1, 6):
			day = getdate(add_days(nowdate(), -back))
			if day.weekday() >= 5:
				continue
			for log_type, hh in (("IN", "08:0"), ("OUT", "17:0")):
				stamp = f"{day} {hh}{RNG.randint(0, 9)}:00"
				if frappe.db.exists("Employee Checkin", {"employee": emp.name, "time": stamp}):
					continue
				if _ensure("Employee Checkin", {"employee": emp.name, "time": stamp}, {
					"employee": emp.name, "time": stamp, "log_type": log_type,
					"device_id": "HQ-DOOR-01",
				}):
					made += 1
	_log("Employee Checkin", f"{frappe.db.count('Employee Checkin')} total (+{made})")

	# Attendance requests (work from home / on duty).
	for i, emp in enumerate(staff[:3]):
		start = add_days(nowdate(), -RNG.randint(60, 90))
		_ensure("Attendance Request", {"employee": emp.name, "from_date": start}, {
			"employee": emp.name, "company": COMPANY,
			"from_date": start, "to_date": start,
			"reason": ["Work From Home", "On Duty", "Work From Home"][i],
			"explanation": "Demo attendance request for training.",
		})
	_log("Attendance Request", f"{frappe.db.count('Attendance Request')} total")

	# Compensatory leave is only valid for work done on an actual holiday - the
	# validator rejects anything else with "<date> is not a holiday". The seeded
	# list declares public holidays but no weekly-off rows, so pick from those.
	hl = frappe.db.get_value("Holiday List", {}, "name")
	past_holidays = [h.holiday_date for h in frappe.get_all(
		"Holiday", filters={"parent": hl, "holiday_date": ["<", nowdate()]},
		fields=["holiday_date"], order_by="holiday_date desc", limit_page_length=5)]
	if not past_holidays:
		_log("Compensatory Leave Request", "no past holidays to claim against")
		past_holidays = []

	for i, emp in enumerate(staff[3:5]):
		if i >= len(past_holidays):
			break
		worked = past_holidays[i]

		# The validator also requires the employee to be marked Present on the day
		# they are claiming for ("You are not present all day(s) between
		# compensatory leave request days"), so mark that attendance first.
		_ensure("Attendance", {"employee": emp.name, "attendance_date": worked}, {
			"employee": emp.name, "attendance_date": worked,
			"status": "Present", "company": COMPANY,
		}, submit=True)
		_ensure("Compensatory Leave Request", {"employee": emp.name, "work_from_date": worked}, {
			"employee": emp.name,
			"work_from_date": worked, "work_end_date": worked,
			"reason": "Worked on a weekend to support a client go-live.",
			"leave_type": "Compensatory Off" if frappe.db.exists("Leave Type", "Compensatory Off")
			              else "Annual Leave",
		})
	_log("Compensatory Leave Request", f"{frappe.db.count('Compensatory Leave Request')} total")

	# Daily work summary group.
	users = [u for u in frappe.get_all("User", filters={"enabled": 1}, pluck="name")
	         if u not in ("Administrator", "Guest")][:5]
	if users:
		_ensure("Daily Work Summary Group", {"name": "Engineering Standup"}, {
			"__newname": "Engineering Standup",
			"users": [{"user": u} for u in users],
			"send_emails_at": "18:00:00",
			"subject": "Daily work summary",
			"message": "Please share what you worked on today.",
			"enabled": 1,
		})
	_log("Daily Work Summary Group", f"{frappe.db.count('Daily Work Summary Group')} total")


# -- reporting hierarchy ------------------------------------------------------

#: subordinate -> manager, by employee name.
#:
#: Drives the organisational chart. Its "N Connections" figure counts an
#: employee's whole reporting subtree (hrms counts descendants with the nested
#: set's lft/rgt), so with no `reports_to` anywhere every node is a root and
#: every card reads "0 Connections".
REPORTING_LINES = {
	# Engineering
	"Baraka Mushi": "Neema Shirima",
	"Samuel Kweka": "Baraka Mushi",
	"Amina Juma": "Baraka Mushi",
	"Joseph Massawe": "Baraka Mushi",
	"Elias Mwakalinga": "Baraka Mushi",
	"Salma Mbwana": "Baraka Mushi",
	# Product & marketing
	"Grace Mollel": "Neema Shirima",
	"Zawadi Lyimo": "Grace Mollel",
	# Sales
	"Daniel Kimaro": "Neema Shirima",
	"Fatuma Said": "Daniel Kimaro",
	"Emmanuel Kessy": "Daniel Kimaro",
	# Finance
	"Peter Ngowi": "Neema Shirima",
	"Rehema Chuwa": "Peter Ngowi",
	# People & operations
	"Anna Mtei": "Neema Shirima",
	"Hamisi Ally": "Neema Shirima",
	# "Neema Shirima" is the root and deliberately has no manager.
}


def seed_reporting_lines() -> None:
	by_name = {e.employee_name: e.name for e in frappe.get_all(
		"Employee", filters={"status": "Active"}, fields=["name", "employee_name"])}

	linked = 0
	for subordinate, manager in REPORTING_LINES.items():
		sub_id, mgr_id = by_name.get(subordinate), by_name.get(manager)
		if not (sub_id and mgr_id) or sub_id == mgr_id:
			continue
		if frappe.db.get_value("Employee", sub_id, "reports_to") == mgr_id:
			continue
		try:
			# Saved through the document, not db.set_value: Employee is a NestedSet
			# and the lft/rgt bounds the chart counts from are only recalculated on
			# save. A direct column write would leave the tree stale and every card
			# still reading "0 Connections".
			doc = frappe.get_doc("Employee", sub_id)
			doc.reports_to = mgr_id
			doc.save(ignore_permissions=True)
			linked += 1
		except Exception as exc:
			_log("Reporting", f"{subordinate}: {str(exc)[:90]}")

	roots = frappe.db.count("Employee", {"status": "Active", "reports_to": ["in", [None, ""]]})
	_log("Reporting lines", f"{linked} linked, {roots} root node(s)")


# -- projects & timesheets ----------------------------------------------------


PROJECTS = [
	("Starrich Careers Portal", "Open", 12_000_000),
	("Payroll Automation Rollout", "Open", 8_500_000),
	("Q3 Sales Campaign", "Open", 5_000_000),
	("Office Relocation - Arusha", "Completed", 3_200_000),
]

TASKS = {
	"Starrich Careers Portal": ["Design job board", "Build application form", "QA and launch"],
	"Payroll Automation Rollout": ["Map salary components", "Parallel run", "Train HR team"],
	"Q3 Sales Campaign": ["Build prospect list", "Run outreach"],
	"Office Relocation - Arusha": ["Fit-out", "Move and setup"],
}


def seed_projects_timesheets(weeks: int = 3) -> None:
	"""Projects, tasks and timesheets.

	These back the Employee Hours Utilization and Project Profitability reports,
	and the timesheet charts, all of which are empty without them.
	"""
	staff = _employees()
	if not staff:
		_log("Timesheets", "no employees")
		return

	made_p = 0
	for name, status, cost in PROJECTS:
		if frappe.db.exists("Project", {"project_name": name}):
			continue
		if _ensure("Project", {"project_name": name}, {
			"project_name": name, "company": COMPANY, "status": status,
			"expected_start_date": add_months(nowdate(), -3),
			"expected_end_date": add_months(nowdate(), 2),
			"estimated_costing": cost,
		}):
			made_p += 1
	_log("Project", f"{frappe.db.count('Project')} total (+{made_p})")

	project_ids = {p.project_name: p.name for p in frappe.get_all(
		"Project", fields=["name", "project_name"])}

	for pname, subjects in TASKS.items():
		pid = project_ids.get(pname)
		if not pid:
			continue
		for subject in subjects:
			_ensure("Task", {"subject": subject, "project": pid}, {
				"subject": subject, "project": pid, "company": COMPANY,
				"status": RNG.choice(["Open", "Working", "Completed"]),
				"exp_start_date": add_months(nowdate(), -2),
				"exp_end_date": add_months(nowdate(), 1),
			})
	_log("Task", f"{frappe.db.count('Task')} total")

	activities = frappe.get_all("Activity Type", pluck="name") or ["Execution"]
	names = list(project_ids.values())
	if not names:
		_log("Timesheet", "no projects to log against")
		return

	made_t = 0
	for emp in staff[:8]:
		for w in range(1, weeks + 1):
			# One timesheet per employee per week, Monday to Wednesday.
			monday = add_days(nowdate(), -(w * 7 + getdate(nowdate()).weekday()))
			if frappe.db.exists("Timesheet", {"employee": emp.name, "start_date": monday,
			                                  "docstatus": ["<", 2]}):
				continue

			logs = []
			for d in range(3):
				day = add_days(monday, d)
				hours = RNG.choice([6, 7, 8])
				logs.append({
					"activity_type": RNG.choice(activities),
					"from_time": f"{day} 09:00:00",
					"hours": hours,
					"project": RNG.choice(names),
					"description": "Demo time log for training.",
					"is_billable": 1,
					"billing_hours": hours,
					"billing_rate": 25_000,
				})

			if _ensure("Timesheet", {"employee": emp.name, "start_date": monday}, {
				"employee": emp.name, "company": COMPANY,
				"start_date": monday, "end_date": add_days(monday, 2),
				"time_logs": logs,
			}, submit=True):
				made_t += 1

	_log("Timesheet", f"{frappe.db.count('Timesheet')} total (+{made_t})")

	# Shift requests, for the Shift & Attendance module.
	#
	# Shift Request validates that the *session user* is the named approver
	# ("Only Approvers can Approve this Request"), so the approver has to be
	# whoever is running the seeder, not an arbitrary HR user.
	# Shift Request only accepts an approver that is already named on the
	# employee's `shift_request_approver` (or the department's approver table);
	# anyone else is rejected with "Only Approvers can Approve this Request".
	approver = frappe.session.user
	shifts = frappe.get_all("Shift Type", pluck="name")
	for i, emp in enumerate(staff[:3]):
		if not shifts:
			break
		if frappe.db.get_value("Employee", emp.name, "shift_request_approver") != approver:
			frappe.db.set_value("Employee", emp.name, "shift_request_approver", approver,
			                    update_modified=False)
		start = add_days(nowdate(), 3 + i)
		_ensure("Shift Request", {"employee": emp.name, "from_date": start}, {
			"employee": emp.name, "company": COMPANY,
			"shift_type": shifts[i % len(shifts)],
			"from_date": start, "to_date": add_days(start, 20),
			"status": "Approved", "approver": approver,
		}, submit=True)
	_log("Shift Request", f"{frappe.db.count('Shift Request')} total")


# -- appraisal scores ---------------------------------------------------------

#: Feedback criteria for the self-appraisal ratings table.
FEEDBACK_CRITERIA = [
	("Quality of Work", 30),
	("Teamwork", 25),
	("Ownership", 25),
	("Communication", 20),
]


def seed_appraisal_scores() -> None:
	"""Fill the score tables behind the Appraisal Overview chart.

	The chart plots Goal / Self / Feedback / Final score, and every one of those
	is *derived* on save from child rows: `appraisal_kra` drives the goal score,
	`self_ratings` the self score, and Employee Performance Feedback records the
	average feedback score. Creating the Appraisal alone leaves all four at zero,
	which is why the chart drew a flat line.
	"""
	appraisals = frappe.get_all("Appraisal", fields=["name", "employee", "appraisal_cycle"])
	if not appraisals:
		_log("Appraisal scores", "no appraisals")
		return

	for name, weight in FEEDBACK_CRITERIA:
		_ensure("Employee Feedback Criteria", {"name": name},
		        {"__newname": name, "criteria": name})

	kras = frappe.get_all("KRA", pluck="name") or []
	# `reviewer` links to Employee, not User - passing a user id fails with
	# "Could not find Reviewer: <email>".
	reviewer = frappe.db.get_value("Employee",
		{"status": "Active", "designation": "HR Manager"}, "name") or \
		frappe.db.get_value("Employee", {"status": "Active"}, "name")

	scored = fed = 0
	for a in appraisals:
		doc = frappe.get_doc("Appraisal", a.name)

		# Goal score.
		#
		# Which table feeds it depends on `rate_goals_manually`: when set (the
		# default here) calculate_total_score() sums `goals`, ignoring
		# `appraisal_kra` entirely - so filling the KRA table alone leaves the
		# goal score at zero.
		if kras:
			if doc.get("rate_goals_manually"):
				if not doc.get("goals"):
					each = round(100 / len(kras), 2)
					weights = [each] * len(kras)
					weights[-1] = round(100 - each * (len(kras) - 1), 2)
					for kra, w in zip(kras, weights):
						doc.append("goals", {
							"kra": kra,
							"per_weightage": w,
							# `score` is out of 5 and is validated against that.
							"score": RNG.choice([3, 3.5, 4, 4.5, 5]),
						})
			else:
				each = round(100 / len(kras), 2)
				weights = [each] * len(kras)
				weights[-1] = round(100 - each * (len(kras) - 1), 2)
				doc.set("appraisal_kra", [])
				for kra, w in zip(kras, weights):
					completion = RNG.choice([70, 80, 85, 90, 95, 100])
					doc.append("appraisal_kra", {
						"kra": kra, "per_weightage": w,
						"goal_completion": completion,
						# total_score = sum(goal_score) / 20
						"goal_score": round(w * completion / 100, 2),
					})

		# Self appraisal ratings. `rating` is 0-1 (Frappe's Rating fieldtype).
		if not doc.get("self_ratings"):
			for crit, w in FEEDBACK_CRITERIA:
				doc.append("self_ratings", {
					"criteria": crit,
					"per_weightage": w,
					"rating": RNG.choice([0.6, 0.7, 0.8, 0.9, 1.0]),
				})

		try:
			doc.save(ignore_permissions=True)   # save recalculates every score
			scored += 1
		except Exception as exc:
			_log("Appraisal", f"{a.name}: {str(exc)[:90]}")
			continue

		# Average feedback score comes from Employee Performance Feedback docs.
		# A reviewer cannot review themselves.
		reviewer_for = reviewer if reviewer != a.employee else frappe.db.get_value(
			"Employee", {"status": "Active", "name": ["!=", a.employee]}, "name")

		if reviewer_for and not frappe.db.exists("Employee Performance Feedback",
		                        {"employee": a.employee, "appraisal": a.name}):
			fb = frappe.get_doc({
				"doctype": "Employee Performance Feedback",
				"employee": a.employee,
				"appraisal": a.name,
				"appraisal_cycle": a.appraisal_cycle,
				"reviewer": reviewer_for,
				"company": COMPANY,
				"added_on": now_str(),
				"feedback": "Consistently dependable, communicates well and delivers on commitments.",
				"feedback_ratings": [
					{"criteria": c, "per_weightage": w,
					 "rating": RNG.choice([0.6, 0.8, 0.9, 1.0])}
					for c, w in FEEDBACK_CRITERIA
				],
			})
			try:
				fb.insert(ignore_permissions=True)
				fb.submit()
				fed += 1
			except Exception as exc:
				_log("Feedback", f"{a.name}: {str(exc)[:90]}")

	_log("Appraisal scores", f"{scored} appraisals scored, {fed} feedback docs")


def now_str() -> str:
	from frappe.utils import now
	return now()


# -- professional tax ---------------------------------------------------------


def seed_professional_tax() -> None:
	"""Make the Professional Tax Deductions report work and return data.

	The report reads `Salary Component.component_type` - a custom field hrms
	creates only in its India regional setup - and lists salary-slip deductions
	whose component is typed "Professional Tax". On a non-India site the field
	does not exist, so opening the report fails with:

	    Unknown column 'component_type' in 'SELECT'

	Creating the field (the same definition hrms uses) plus a typed component and
	slips that carry it makes the report work as designed.
	"""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	if not frappe.get_meta("Salary Component").has_field("component_type"):
		create_custom_fields({
			"Salary Component": [{
				"fieldname": "component_type",
				"label": "Component Type",
				"fieldtype": "Select",
				"insert_after": "description",
				"options": "\nProvident Fund\nAdditional Provident Fund\nProvident Fund Loan\nProfessional Tax",
				"depends_on": 'eval:doc.type == "Deduction"',
				"translatable": 0,
			}]
		}, ignore_validate=True)
		frappe.db.commit()
	_log("component_type field", "present")

	COMPONENT = "Professional Tax"
	_ensure("Salary Component", {"salary_component": COMPONENT}, {
		"salary_component": COMPONENT, "type": "Deduction",
		"salary_component_abbr": "PT",
		"component_type": COMPONENT,
		"description": "Statutory professional tax deduction.",
	})
	# `component_type` is what the report filters on, so make sure it is set even
	# if the component already existed without it.
	if frappe.db.exists("Salary Component", COMPONENT):
		frappe.db.set_value("Salary Component", COMPONENT, "component_type", COMPONENT,
		                    update_modified=False)
	_log("Salary Component", f"{COMPONENT} typed as {COMPONENT}")

	# A second structure carrying the deduction.
	#
	# The original structure cannot simply be amended: it has submitted Salary
	# Structure Assignments against it, so cancelling it is refused. A parallel
	# structure keeps the existing payroll history intact.
	PT_STRUCTURE = "Starrich Salary (with PT)"
	base_structure = "Starrich Standard Salary"

	if not frappe.db.exists("Salary Structure", PT_STRUCTURE) and \
			frappe.db.exists("Salary Structure", base_structure):
		src = frappe.get_doc("Salary Structure", base_structure)
		doc = frappe.copy_doc(src)
		doc.name = PT_STRUCTURE
		doc.__newname = PT_STRUCTURE
		doc.docstatus = 0
		doc.append("deductions", {"salary_component": COMPONENT, "amount": 15_000})
		try:
			doc.insert(ignore_permissions=True)
			doc.submit()
			frappe.db.commit()
		except Exception as exc:
			frappe.db.rollback()
			_log("Salary Structure", f"PT structure: {str(exc)[:90]}")
	_log("Salary Structure", f"{PT_STRUCTURE} present: {frappe.db.exists('Salary Structure', PT_STRUCTURE)}")

	if not frappe.db.exists("Salary Structure", PT_STRUCTURE):
		return

	# Current-month slips on the new structure. These also give Salary Register
	# rows inside its default date window, which the previous month's slips miss.
	start = getdate(nowdate()).replace(day=1)
	assigned = made = 0
	for emp in _employees()[:6]:
		base = flt(frappe.db.get_value("Employee Grade", emp.grade, "default_base_pay")) or 1_200_000
		if not frappe.db.exists("Salary Structure Assignment",
		                        {"employee": emp.name, "salary_structure": PT_STRUCTURE}):
			if _ensure("Salary Structure Assignment",
				{"employee": emp.name, "salary_structure": PT_STRUCTURE},
				{
					"employee": emp.name, "salary_structure": PT_STRUCTURE,
					"from_date": start, "company": COMPANY, "base": base,
					"income_tax_slab": frappe.db.get_value(
						"Income Tax Slab", {"company": COMPANY, "docstatus": 1}, "name"),
				}, submit=True):
				assigned += 1

		if frappe.db.exists("Salary Slip", {"employee": emp.name, "start_date": start,
		                                    "docstatus": ["<", 2]}):
			continue
		if _ensure("Salary Slip", {"employee": emp.name, "start_date": start}, {
			"employee": emp.name, "company": COMPANY,
			"salary_structure": PT_STRUCTURE, "start_date": start,
			"payroll_frequency": "Monthly",
		}, submit=True):
			made += 1

	_log("PT assignments", f"+{assigned}")
	_log("Salary Slip (this month)", f"+{made}")
