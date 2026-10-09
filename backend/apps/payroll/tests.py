from datetime import date, timedelta
from decimal import Decimal

from django.test import SimpleTestCase

from apps.payroll.engine import build_month_facts, calculate_pay


def policy(**overrides):
    base = {
        "salary_divisor_mode": "scheduled_working_days",
        "fixed_salary_divisor": Decimal("30"),
        "standard_work_minutes": 480,
        "overtime_multiplier": Decimal("1.5"),
        "holiday_work_counts_as_overtime": True,
        "unpaid_leave_deduction_enabled": True,
        "absence_deduction_enabled": False,
        "late_penalty_enabled": False,
        "late_penalty_mode": "per_occurrence",
        "late_penalty_amount": Decimal("0"),
        "daily_wage_pays_weekly_off": False,
        "daily_wage_pays_holiday": False,
        "daily_wage_pays_paid_leave": True,
    }
    base.update(overrides)
    return base


def present_month(year, month, offs=None, holidays=None, skip=None, overrides=None):
    offs = offs or {5, 6}
    holidays = holidays or set()
    skip = set(skip or [])
    overrides = overrides or {}
    import calendar

    attendance = {}
    last = calendar.monthrange(year, month)[1]
    for day_number in range(1, last + 1):
        day = date(year, month, day_number)
        if day.weekday() in offs or day in holidays or day in skip:
            continue
        attendance[day] = {
            "status": "present",
            "late_minutes": 0,
            "early_departure_minutes": 0,
            "working_minutes": 420,
            "overtime_minutes": 0,
            "is_incomplete": False,
        }
        attendance[day].update(overrides.get(day, {}))
    return attendance


def run_month(employee, attendance, leaves=None, holidays=None, offs=None, today=None, rules=None):
    year = employee["year"]
    month = employee["month"]
    import calendar

    last = calendar.monthrange(year, month)[1]
    facts, warnings = build_month_facts(
        year=year,
        month=month,
        joining_date=employee["joining_date"],
        exit_date=employee.get("exit_date"),
        weekly_off_days=offs or {5, 6},
        holiday_dates=holidays or set(),
        attendance=attendance,
        leaves=leaves or [],
        today=today or date(year, month, last),
    )
    return calculate_pay(policy=rules or policy(), employee=employee, facts=facts, today=today or date(year, month, last), warnings=warnings)


class PayrollEngineTests(SimpleTestCase):
    def test_full_month_pays_basic_without_deducting_weekly_offs(self):
        employee = {
            "salary_type": "monthly",
            "basic_salary": Decimal("2200"),
            "joining_date": date(2024, 1, 1),
            "exit_date": None,
            "year": 2026,
            "month": 10,
            "allowance_lines": [{"label": "Transport", "amount": Decimal("100")}],
        }
        result = run_month(employee, present_month(2026, 10), today=date(2026, 11, 1))
        self.assertEqual(result["totals"]["net_salary"], Decimal("2300.00"))
        self.assertEqual(result["counts"]["absent_days"], Decimal("0.00"))
        self.assertGreater(result["counts"]["weekly_offs"], 0)

    def test_public_holiday_and_paid_leave_are_not_deducted(self):
        holiday = date(2026, 10, 2)
        employee = {
            "salary_type": "monthly",
            "basic_salary": Decimal("2200"),
            "joining_date": date(2024, 1, 1),
            "year": 2026,
            "month": 10,
        }
        attendance = present_month(2026, 10, holidays={holiday}, skip={date(2026, 10, 5)})
        result = run_month(
            employee,
            attendance,
            leaves=[{"start": date(2026, 10, 5), "end": date(2026, 10, 5), "day_part": "full", "is_paid": True, "status": "approved"}],
            holidays={holiday},
            today=date(2026, 11, 1),
        )
        self.assertEqual(result["totals"]["net_salary"], Decimal("2200.00"))
        self.assertEqual(result["counts"]["public_holidays"], 1)
        self.assertEqual(result["counts"]["paid_leave_days"], Decimal("1.00"))
        self.assertEqual(result["counts"]["absent_days"], Decimal("0.00"))

    def test_unpaid_leave_is_deducted_once(self):
        employee = {
            "salary_type": "monthly",
            "basic_salary": Decimal("2200"),
            "joining_date": date(2024, 1, 1),
            "year": 2026,
            "month": 10,
        }
        day = date(2026, 10, 5)
        attendance = present_month(2026, 10, skip={day})
        result = run_month(
            employee,
            attendance,
            leaves=[{"start": day, "end": day, "day_part": "full", "is_paid": False, "status": "approved"}],
            today=date(2026, 11, 1),
        )
        self.assertEqual(result["counts"]["unpaid_leave_days"], Decimal("1.00"))
        self.assertEqual(result["counts"]["absent_days"], Decimal("0.00"))
        self.assertEqual(result["components"]["unpaid_leave_deduction"], Decimal("100.00"))
        self.assertEqual(result["totals"]["net_salary"], Decimal("2100.00"))

    def test_absence_deduction_is_optional_and_not_doubled_with_unpaid_leave(self):
        employee = {
            "salary_type": "monthly",
            "basic_salary": Decimal("2200"),
            "joining_date": date(2024, 1, 1),
            "year": 2026,
            "month": 10,
        }
        unpaid = date(2026, 10, 5)
        absent = date(2026, 10, 6)
        attendance = present_month(2026, 10, skip={unpaid, absent})
        result = run_month(
            employee,
            attendance,
            leaves=[{"start": unpaid, "end": unpaid, "day_part": "full", "is_paid": False, "status": "approved"}],
            today=date(2026, 11, 1),
            rules=policy(absence_deduction_enabled=True),
        )
        self.assertEqual(result["components"]["unpaid_leave_deduction"], Decimal("100.00"))
        self.assertEqual(result["components"]["attendance_deduction"], Decimal("100.00"))
        self.assertEqual(result["totals"]["net_salary"], Decimal("2000.00"))

    def test_late_penalty_stays_off_until_enabled(self):
        employee = {
            "salary_type": "monthly",
            "basic_salary": Decimal("2200"),
            "joining_date": date(2024, 1, 1),
            "year": 2026,
            "month": 10,
        }
        late_day = date(2026, 10, 1)
        attendance = present_month(2026, 10, overrides={late_day: {"status": "late", "late_minutes": 25}})
        quiet = run_month(employee, attendance, today=date(2026, 11, 1))
        self.assertEqual(quiet["components"]["late_penalty"], Decimal("0.00"))
        self.assertIn("no late-arrival penalty", " ".join(quiet["warnings"]))
        penalized = run_month(
            employee,
            attendance,
            today=date(2026, 11, 1),
            rules=policy(late_penalty_enabled=True, late_penalty_amount=Decimal("15")),
        )
        self.assertEqual(penalized["components"]["late_penalty"], Decimal("15.00"))
        self.assertEqual(penalized["totals"]["net_salary"], Decimal("2185.00"))

    def test_mid_month_joiner_is_prorated_on_scheduled_days(self):
        employee = {
            "salary_type": "monthly",
            "basic_salary": Decimal("3100"),
            "joining_date": date(2026, 10, 15),
            "year": 2026,
            "month": 10,
        }
        attendance = present_month(2026, 10)
        result = run_month(employee, attendance, today=date(2026, 11, 1))
        self.assertEqual(result["counts"]["employed_scheduled_days"], 12)
        self.assertEqual(result["counts"]["full_month_scheduled_days"], 22)
        self.assertEqual(result["totals"]["net_salary"], Decimal("1690.91"))

    def test_fixed_divisor_full_month_is_not_shrunk(self):
        employee = {
            "salary_type": "monthly",
            "basic_salary": Decimal("3000"),
            "joining_date": date(2024, 1, 1),
            "year": 2026,
            "month": 10,
        }
        result = run_month(employee, present_month(2026, 10), today=date(2026, 11, 1), rules=policy(salary_divisor_mode="fixed"))
        self.assertEqual(result["totals"]["net_salary"], Decimal("3000.00"))

    def test_daily_wage_does_not_pay_weekly_offs_by_default(self):
        employee = {
            "salary_type": "daily",
            "basic_salary": Decimal("0"),
            "daily_rate": Decimal("40"),
            "joining_date": date(2024, 1, 1),
            "year": 2026,
            "month": 10,
        }
        result = run_month(employee, present_month(2026, 10), today=date(2026, 11, 1))
        self.assertEqual(result["counts"]["present_days"], Decimal("22.00"))
        self.assertEqual(result["totals"]["net_salary"], Decimal("880.00"))

    def test_half_day_counts_half_and_holiday_overtime_is_extra_for_monthly_pay(self):
        employee = {
            "salary_type": "monthly",
            "basic_salary": Decimal("2200"),
            "joining_date": date(2024, 1, 1),
            "year": 2026,
            "month": 10,
        }
        holiday = date(2026, 10, 2)
        attendance = present_month(2026, 10, holidays={holiday}, overrides={date(2026, 10, 1): {"status": "half_day", "working_minutes": 180}})
        attendance[holiday] = {
            "status": "holiday_worked",
            "late_minutes": 0,
            "early_departure_minutes": 0,
            "working_minutes": 480,
            "overtime_minutes": 480,
            "is_incomplete": False,
        }
        plain = run_month(employee, attendance, holidays={holiday}, today=date(2026, 11, 1), rules=policy(absence_deduction_enabled=True))
        self.assertEqual(plain["counts"]["half_days"], 1)
        self.assertEqual(plain["counts"]["full_month_scheduled_days"], 21)
        self.assertEqual(plain["components"]["attendance_deduction"], Decimal("52.38"))
        self.assertEqual(plain["components"]["overtime_pay"], Decimal("157.14"))

    def test_incomplete_late_check_in_counts_as_late_without_becoming_an_absence(self):
        employee = {
            "salary_type": "monthly",
            "basic_salary": Decimal("2200"),
            "joining_date": date(2024, 1, 1),
            "year": 2026,
            "month": 10,
        }
        day = date(2026, 10, 8)
        attendance = present_month(2026, 10, skip={day})
        attendance[day] = {
            "status": "incomplete",
            "late_minutes": 40,
            "early_departure_minutes": 0,
            "working_minutes": 0,
            "overtime_minutes": 0,
            "is_incomplete": True,
        }
        result = run_month(employee, attendance, today=day)
        self.assertEqual(result["counts"]["late_count"], 1)
        self.assertEqual(result["counts"]["absent_days"], Decimal("0.00"))
        self.assertEqual(result["components"]["late_penalty"], Decimal("0.00"))
