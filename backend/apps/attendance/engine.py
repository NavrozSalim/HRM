"""Pure shift math. Times must be timezone-aware datetimes."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo


class TimeError(ValueError):
    pass


def shift_bounds(day, start: time, end: time, overnight: bool, tz_name: str):
    tz = ZoneInfo(tz_name)
    start_dt = datetime.combine(day, start, tzinfo=tz)
    crosses = bool(overnight or end <= start)
    end_dt = datetime.combine(day + (timedelta(days=1) if crosses else timedelta()), end, tzinfo=tz)
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)
        crosses = True
    return start_dt, end_dt, crosses


def evaluate_times(
    *,
    day,
    tz_name: str,
    shift_start: time,
    shift_end: time,
    overnight: bool,
    break_minutes: int,
    grace_minutes: int,
    early_grace_minutes: int,
    half_day_threshold_minutes: int,
    check_in: datetime | None,
    check_out: datetime | None,
    is_weekly_off: bool,
    is_holiday: bool,
    has_leave: bool,
    holiday_work_is_overtime: bool = True,
    forced_status: str | None = None,
    today=None,
) -> dict:
    start_dt, end_dt, crosses = shift_bounds(day, shift_start, shift_end, overnight, tz_name)
    scheduled = max(0, int((end_dt - start_dt).total_seconds() // 60) - int(break_minutes or 0))

    if check_in and check_in.tzinfo is None:
        raise TimeError("Check-in must include a time zone.")
    if check_out and check_out.tzinfo is None:
        raise TimeError("Check-out must include a time zone.")
    if check_in and check_out and check_out <= check_in:
        raise TimeError("Check-out must be after check-in.")

    late = 0
    early = 0
    working = 0
    overtime = 0
    incomplete = False

    if check_in:
        grace_end = start_dt + timedelta(minutes=int(grace_minutes or 0))
        if check_in > grace_end:
            late = int((check_in - start_dt).total_seconds() // 60)

    if check_in and not check_out:
        incomplete = True
    elif check_in and check_out:
        gross = int((check_out - check_in).total_seconds() // 60)
        working = max(0, gross - int(break_minutes or 0))
        early_cutoff = end_dt - timedelta(minutes=int(early_grace_minutes or 0))
        if check_out < early_cutoff:
            early = int((end_dt - check_out).total_seconds() // 60)
        if is_holiday or is_weekly_off:
            overtime = working if holiday_work_is_overtime else max(0, working - scheduled)
        else:
            overtime = max(0, working - scheduled)

    if forced_status:
        status = forced_status
    elif incomplete:
        status = "incomplete"
    elif not check_in and not check_out:
        if is_holiday:
            status = "public_holiday"
        elif is_weekly_off:
            status = "weekly_off"
        elif has_leave:
            status = "on_leave"
        elif today is not None and day >= today:
            status = "unmarked"
        else:
            status = "absent"
    elif is_holiday and working > 0:
        status = "holiday_worked"
    elif is_weekly_off and working > 0:
        status = "off_worked"
    elif is_holiday:
        status = "public_holiday"
    elif is_weekly_off:
        status = "weekly_off"
    elif working <= 0:
        status = "absent"
    elif half_day_threshold_minutes and working < int(half_day_threshold_minutes):
        status = "half_day"
    elif late > 0:
        status = "late"
    else:
        status = "present"

    return {
        "status": status,
        "late_minutes": late,
        "early_departure_minutes": early,
        "working_minutes": working,
        "overtime_minutes": overtime,
        "scheduled_minutes": scheduled,
        "is_incomplete": bool(incomplete or status == "incomplete"),
        "shift_overnight": crosses,
        "shift_start_dt": start_dt,
        "shift_end_dt": end_dt,
    }
