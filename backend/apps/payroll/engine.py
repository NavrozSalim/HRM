"""Pure month classification and salary math.

Monthly gross = prorated basic + allowances + bonuses + overtime.
Monthly net = gross - approved deductions - unpaid leave - optional absence
deductions - optional late penalties - advances - other adjustments.

Weekly offs and public holidays are not unauthorized absences.
Approved paid leave is not deducted.
An unpaid leave day is not also deducted as an absence.
Late penalties and attendance deductions stay at zero unless that policy is enabled.
A full-month employee keeps their full basic salary. The divisor is used for the
day rate and for mid-month proration, not to shrink a complete month.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from decimal import Decimal

ZERO = Decimal("0")
ONE = Decimal("1")
HALF = Decimal("0.5")
TWOPLACES = Decimal("0.01")


def D(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None or value == "":
        return ZERO
    return Decimal(str(value))


def money(value) -> Decimal:
    return D(value).quantize(TWOPLACES)


def _daterange(start: date, end: date):
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def _leave_fractions(leaves: list[dict], day: date) -> tuple[Decimal, Decimal]:
    paid = ZERO
    unpaid = ZERO
    for leave in leaves:
        if leave.get("status", "approved") != "approved":
            continue
        if leave["start"] <= day <= leave["end"]:
            fraction = HALF if leave.get("day_part", "full") != "full" else ONE
            if leave.get("is_paid", True):
                paid += fraction
            else:
                unpaid += fraction
    if paid + unpaid > ONE:
        scale = paid + unpaid
        paid = (paid / scale).quantize(TWOPLACES)
        unpaid = (ONE - paid) if unpaid else ZERO
    return paid, unpaid


def build_month_facts(
    *,
    year: int,
    month: int,
    joining_date: date,
    exit_date: date | None,
    weekly_off_days: set[int],
    holiday_dates: set[date],
    attendance: dict[date, dict],
    leaves: list[dict],
    today: date,
) -> tuple[list[dict], list[str]]:
    last_day = calendar.monthrange(year, month)[1]
    facts = []
    warnings = []

    for day in _daterange(date(year, month, 1), date(year, month, last_day)):
        employed = joining_date <= day and (exit_date is None or day <= exit_date)
        calendar_off = day.weekday() in weekly_off_days
        calendar_holiday = day in holiday_dates
        calendar_workday = not calendar_off and not calendar_holiday
        record = attendance.get(day) if employed else None
        status = record.get("status") if record else None
        late_minutes = int((record or {}).get("late_minutes") or 0)
        early_minutes = int((record or {}).get("early_departure_minutes") or 0)
        working_minutes = int((record or {}).get("working_minutes") or 0)
        overtime_minutes = int((record or {}).get("overtime_minutes") or 0)
        incomplete = bool((record or {}).get("is_incomplete") or status == "incomplete")

        if record and status in {"weekly_off", "off_worked"}:
            is_off, is_holiday = True, False
        elif record and status in {"public_holiday", "holiday_worked"}:
            is_off, is_holiday = False, True
        elif record:
            is_off, is_holiday = False, False
        else:
            is_off, is_holiday = calendar_off, calendar_holiday

        scheduled = bool(employed and not is_off and not is_holiday)
        if status in {"present", "late", "holiday_worked", "off_worked"}:
            present = ONE
        elif status == "half_day":
            present = HALF
        else:
            present = ZERO

        paid_leave = ZERO
        unpaid_leave = ZERO
        absent = ZERO
        unmarked = False

        if not employed:
            present = ZERO
            scheduled = False
            incomplete = False
            is_off = False
            is_holiday = False
        elif not scheduled:
            if status not in {"holiday_worked", "off_worked", "present", "late", "half_day"}:
                present = ZERO
        else:
            paid_leave, unpaid_leave = _leave_fractions(leaves, day)
            if status == "absent":
                present = ZERO
                if paid_leave + unpaid_leave > ZERO:
                    warnings.append(
                        f"{day.isoformat()}: an absence mark overlaps approved leave. "
                        "Leave was kept so the day is not deducted twice."
                    )
                    absent = max(ZERO, ONE - paid_leave - unpaid_leave)
                else:
                    paid_leave = ZERO
                    unpaid_leave = ZERO
                    absent = ONE
            else:
                if present + paid_leave + unpaid_leave > ONE:
                    warnings.append(
                        f"{day.isoformat()}: attendance and leave overlap. "
                        "The day was capped at one so it is not paid or deducted twice."
                    )
                    overflow = present + paid_leave + unpaid_leave - ONE
                    take = min(unpaid_leave, overflow)
                    unpaid_leave -= take
                    overflow -= take
                    take = min(paid_leave, overflow)
                    paid_leave -= take
                    overflow -= take
                    present = max(ZERO, present - overflow)
                covered = present + paid_leave + unpaid_leave
                remainder = ONE - covered
                if incomplete and present == ZERO:
                    absent = ZERO
                    warnings.append(
                        f"{day.isoformat()}: incomplete attendance was left unresolved. "
                        "It was not treated as a full day or as an absence."
                    )
                elif covered == ZERO and day < today:
                    absent = ONE
                elif covered == ZERO and day == today:
                    unmarked = True
                elif remainder == ZERO or day > today:
                    absent = ZERO
                elif day < today or status == "half_day":
                    absent = remainder
                else:
                    unmarked = True

        facts.append(
            {
                "date": day,
                "employed": employed,
                "calendar_workday": calendar_workday,
                "scheduled": scheduled,
                "weekly_off": bool(employed and is_off),
                "holiday": bool(employed and is_holiday),
                "status": status,
                "present": present,
                "absent": absent,
                "paid_leave": paid_leave if scheduled else ZERO,
                "unpaid_leave": unpaid_leave if scheduled else ZERO,
                "late_minutes": late_minutes if scheduled else 0,
                "early_minutes": early_minutes if scheduled else 0,
                "working_minutes": working_minutes if employed else 0,
                "overtime_minutes": overtime_minutes if employed else 0,
                "incomplete": bool(incomplete and scheduled),
                "unmarked": unmarked,
                "half_day": bool(scheduled and status == "half_day"),
                "late": bool(scheduled and late_minutes > 0 and status in {"late", "half_day", "incomplete"}),
            }
        )
    return facts, warnings


def _sum(facts, key, predicate=lambda fact: True) -> Decimal:
    total = ZERO
    for fact in facts:
        if predicate(fact):
            total += D(fact[key])
    return total


def consecutive_absences(facts, today: date) -> int:
    streak = 0
    for fact in reversed(facts):
        if fact["date"] > today:
            continue
        if not fact["scheduled"]:
            continue
        if fact["absent"] >= ONE:
            streak += 1
        else:
            break
    return streak


def totals_from_lines(lines: list[dict]) -> dict:
    gross = sum((money(line["amount"]) for line in lines if line["kind"] == "earning"), ZERO)
    deductions = sum((money(line["amount"]) for line in lines if line["kind"] == "deduction"), ZERO)
    return {"gross_salary": money(gross), "total_deductions": money(deductions), "net_salary": money(gross - deductions)}


def _line(kind, code, label, amount, **extra):
    quantized = money(amount)
    if quantized == ZERO and code != "basic":
        return None
    item = {"kind": kind, "code": code, "label": label, "amount": quantized, "is_manual": False}
    item.update(extra)
    return item


def calculate_pay(*, policy: dict, employee: dict, facts: list[dict], today: date, extras: dict | None = None, warnings: list[str] | None = None) -> dict:
    extras = extras or {}
    warnings = list(warnings or [])
    year = int(employee["year"])
    month = int(employee["month"])
    salary_type = employee["salary_type"]
    basic = D(employee.get("basic_salary") or 0)
    joining = employee["joining_date"]
    exit_date = employee.get("exit_date")
    cal_days = calendar.monthrange(year, month)[1]
    month_start = date(year, month, 1)
    month_end = date(year, month, cal_days)
    partial = joining > month_start or (exit_date is not None and exit_date < month_end)

    full_scheduled = sum(1 for fact in facts if fact["calendar_workday"])
    employed_scheduled = sum(1 for fact in facts if fact["calendar_workday"] and fact["employed"])
    employed_calendar = sum(1 for fact in facts if fact["employed"])
    mode = policy.get("salary_divisor_mode") or "scheduled_working_days"
    if mode == "calendar_days":
        divisor = D(cal_days)
    elif mode == "fixed":
        divisor = D(policy.get("fixed_salary_divisor") or 30)
    else:
        divisor = D(full_scheduled or cal_days)
    if divisor <= 0:
        divisor = D(cal_days or 1)

    if not partial:
        prorated_basic = basic
        allowance_factor = ONE
    elif mode == "scheduled_working_days":
        allowance_factor = D(employed_scheduled) / D(full_scheduled or 1)
        prorated_basic = basic * allowance_factor
    elif mode == "fixed":
        prorated_basic = (basic / divisor) * D(employed_calendar)
        allowance_factor = D(employed_calendar) / D(cal_days)
    else:
        allowance_factor = D(employed_calendar) / D(cal_days)
        prorated_basic = basic * allowance_factor

    per_day = basic / divisor
    present_days = _sum(facts, "present", lambda fact: fact["scheduled"])
    absent_days = _sum(facts, "absent", lambda fact: fact["scheduled"])
    paid_leave_days = _sum(facts, "paid_leave", lambda fact: fact["scheduled"])
    unpaid_leave_days = _sum(facts, "unpaid_leave", lambda fact: fact["scheduled"])
    elapsed = [fact for fact in facts if fact["scheduled"] and fact["date"] <= today]
    attended = sum((fact["present"] + fact["paid_leave"] for fact in elapsed), ZERO)
    attendance_percentage = (attended / D(len(elapsed)) * Decimal("100")) if elapsed else ZERO
    considered = [
        fact
        for fact in elapsed
        if fact["status"] in {"present", "late", "half_day"} or (fact["status"] == "incomplete" and fact["late"])
    ]
    on_time = [fact for fact in considered if not fact["late"]]
    punctuality = (D(len(on_time)) / D(len(considered)) * Decimal("100")) if considered else None
    late_count = sum(1 for fact in facts if fact["late"] and fact["date"] <= today)
    late_minutes = sum(fact["late_minutes"] for fact in facts if fact["date"] <= today)
    early_departures = sum(1 for fact in facts if fact["scheduled"] and fact["early_minutes"] > 0 and fact["date"] <= today)
    half_days = sum(1 for fact in facts if fact["half_day"])
    weekly_offs = sum(1 for fact in facts if fact["weekly_off"])
    holidays = sum(1 for fact in facts if fact["holiday"])
    working_minutes = sum(fact["working_minutes"] for fact in facts if fact["employed"])
    overtime_minutes = sum(fact["overtime_minutes"] for fact in facts if fact["employed"])
    payable_ot = 0
    for fact in facts:
        if not fact["employed"]:
            continue
        if fact["scheduled"] or (salary_type in {"monthly", "hourly"} and policy.get("holiday_work_counts_as_overtime", True)):
            payable_ot += fact["overtime_minutes"]

    multiplier = D(policy.get("overtime_multiplier") or 1)
    standard_hours = D(policy.get("standard_work_minutes") or 480) / Decimal("60")
    hourly_from_monthly = (per_day / standard_hours) if standard_hours else ZERO

    if salary_type == "hourly":
        rate = D(employee.get("hourly_rate") or 0)
        if rate <= 0:
            warnings.append("Hourly wage is zero, so no wage was calculated.")
        regular_minutes = max(0, working_minutes - payable_ot)
        base_pay = rate * D(regular_minutes) / Decimal("60")
        overtime_pay = rate * multiplier * D(payable_ot) / Decimal("60")
        basic_label = "Hourly wages"
    elif salary_type == "daily":
        rate = D(employee.get("daily_rate") or 0)
        if rate <= 0:
            warnings.append("Daily rate is zero, so no wage was calculated.")
        base_pay = rate * present_days
        if policy.get("daily_wage_pays_paid_leave", True):
            base_pay += rate * paid_leave_days
        if policy.get("daily_wage_pays_holiday"):
            base_pay += rate * D(holidays)
        else:
            base_pay += rate * _sum(facts, "present", lambda fact: fact["holiday"])
        if policy.get("daily_wage_pays_weekly_off"):
            base_pay += rate * D(weekly_offs)
        else:
            base_pay += rate * _sum(facts, "present", lambda fact: fact["weekly_off"])
        hourly_from_daily = (rate / standard_hours) if standard_hours else ZERO
        scheduled_ot = sum(fact["overtime_minutes"] for fact in facts if fact["scheduled"])
        overtime_pay = hourly_from_daily * multiplier * D(scheduled_ot) / Decimal("60")
        basic_label = "Daily wages"
    else:
        base_pay = prorated_basic
        overtime_pay = hourly_from_monthly * multiplier * D(payable_ot) / Decimal("60")
        basic_label = "Basic salary"

    allowance_lines = employee.get("allowance_lines") or []
    if not allowance_lines and D(employee.get("allowances") or 0) > 0:
        allowance_lines = [{"label": "Allowances", "amount": employee.get("allowances")}]
    allowance_total = ZERO
    prepared_allowances = []
    for entry in allowance_lines:
        amount = money(D(entry["amount"]) * allowance_factor)
        if amount <= 0:
            continue
        allowance_total += amount
        prepared_allowances.append((entry.get("label") or "Allowance", amount))

    bonus_total = ZERO
    prepared_bonuses = []
    for entry in extras.get("bonuses") or []:
        amount = money(entry["amount"])
        if amount <= 0:
            continue
        bonus_total += amount
        prepared_bonuses.append((entry.get("label") or "Bonus", amount))

    deduction_total = ZERO
    prepared_deductions = []
    for entry in extras.get("deductions") or []:
        amount = money(entry["amount"])
        if amount <= 0:
            continue
        deduction_total += amount
        prepared_deductions.append((entry.get("label") or "Deduction", amount))

    advance_total = money(extras.get("advances") or 0)

    unpaid_deduction = ZERO
    absence_deduction = ZERO
    if salary_type == "monthly":
        if policy.get("unpaid_leave_deduction_enabled", True) and unpaid_leave_days > 0:
            unpaid_deduction = per_day * unpaid_leave_days
        elif unpaid_leave_days > 0:
            warnings.append("Unpaid leave was not deducted because that policy is turned off.")
        if policy.get("absence_deduction_enabled") and absent_days > 0:
            absence_deduction = per_day * absent_days
        elif absent_days > 0:
            warnings.append("Unauthorized absences were not deducted because attendance-based deductions are turned off.")
    elif unpaid_leave_days > 0 or absent_days > 0:
        warnings.append("Daily and hourly wages are paid for worked or payable days, so unpaid time is not deducted a second time.")

    late_penalty = ZERO
    if policy.get("late_penalty_enabled") and late_count:
        amount = D(policy.get("late_penalty_amount") or 0)
        if policy.get("late_penalty_mode") == "per_minute":
            late_penalty = amount * D(late_minutes)
        else:
            late_penalty = amount * D(late_count)
    elif late_count:
        warnings.append("Late arrivals were not deducted because no late-arrival penalty has been enabled.")

    lines = []
    basic_line = _line("earning", "basic", basic_label, base_pay)
    if basic_line:
        lines.append(basic_line)
    else:
        lines.append({"kind": "earning", "code": "basic", "label": basic_label, "amount": money(0), "is_manual": False})
    for index, (label, amount) in enumerate(prepared_allowances, start=1):
        lines.append({"kind": "earning", "code": f"allowance_{index}", "label": label, "amount": amount, "is_manual": False})
    for index, (label, amount) in enumerate(prepared_bonuses, start=1):
        lines.append({"kind": "earning", "code": f"bonus_{index}", "label": label, "amount": amount, "is_manual": False})
    overtime_line = _line("earning", "overtime", "Overtime pay", overtime_pay)
    if overtime_line:
        lines.append(overtime_line)
    for index, (label, amount) in enumerate(prepared_deductions, start=1):
        lines.append({"kind": "deduction", "code": f"approved_{index}", "label": label, "amount": amount, "is_manual": False})
    for code, label, amount in (
        ("unpaid_leave", "Unpaid leave deduction", unpaid_deduction),
        ("absence", "Attendance deduction", absence_deduction),
        ("late_penalty", "Late arrival penalty", late_penalty),
        ("advance", "Salary advance recovery", advance_total),
    ):
        line = _line("deduction", code, label, amount)
        if line:
            lines.append(line)

    totals = totals_from_lines(lines)
    counts = {
        "calendar_days": cal_days,
        "divisor": money(divisor),
        "divisor_mode": mode,
        "per_day_rate": money(per_day),
        "full_month_scheduled_days": full_scheduled,
        "employed_scheduled_days": employed_scheduled,
        "scheduled_working_days": sum(1 for fact in facts if fact["scheduled"]),
        "elapsed_scheduled_days": len(elapsed),
        "present_days": money(present_days),
        "absent_days": money(absent_days),
        "half_days": half_days,
        "paid_leave_days": money(paid_leave_days),
        "unpaid_leave_days": money(unpaid_leave_days),
        "weekly_offs": weekly_offs,
        "public_holidays": holidays,
        "late_count": late_count,
        "late_minutes": late_minutes,
        "early_departures": early_departures,
        "working_hours": money(D(working_minutes) / Decimal("60")),
        "overtime_hours": money(D(overtime_minutes) / Decimal("60")),
        "attendance_percentage": money(attendance_percentage),
        "punctuality_percentage": None if punctuality is None else money(punctuality),
        "consecutive_absences": consecutive_absences(facts, today),
        "incomplete_days": sum(1 for fact in facts if fact["incomplete"]),
        "partial_employment": partial,
    }
    return {
        "salary_type": salary_type,
        "lines": lines,
        "warnings": warnings,
        "counts": counts,
        "totals": totals,
        "components": {
            "basic_salary": money(base_pay),
            "allowances_total": money(allowance_total),
            "bonuses_total": money(bonus_total),
            "overtime_pay": money(overtime_pay),
            "approved_deductions": money(deduction_total),
            "unpaid_leave_deduction": money(unpaid_deduction),
            "attendance_deduction": money(absence_deduction),
            "late_penalty": money(late_penalty),
            "advances_total": money(advance_total),
        },
        "formula": [
            "Gross = basic or wages + allowances + bonuses + overtime",
            "Net = gross - approved deductions - unpaid leave - attendance deductions - late penalties - advances - other adjustments",
            "Weekly offs and public holidays are not deducted.",
            "Approved paid leave is not an unpaid absence.",
            "Unpaid leave is not deducted again as an absence.",
            f"Day rate uses {mode.replace('_', ' ')} ({money(divisor)}).",
        ],
    }
