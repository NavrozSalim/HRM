from datetime import datetime, time
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase

from apps.attendance.engine import TimeError, evaluate_times


def punch(day, hour, minute, tz="Asia/Karachi"):
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=ZoneInfo(tz))


class AttendanceEngineTests(SimpleTestCase):
    def test_grace_period_and_late_minutes_from_shift_start(self):
        day = datetime(2026, 10, 5).date()
        within = evaluate_times(
            day=day,
            tz_name="Asia/Karachi",
            shift_start=time(9, 0),
            shift_end=time(17, 0),
            overnight=False,
            break_minutes=60,
            grace_minutes=10,
            early_grace_minutes=10,
            half_day_threshold_minutes=240,
            check_in=punch(day, 9, 9),
            check_out=punch(day, 17, 0),
            is_weekly_off=False,
            is_holiday=False,
            has_leave=False,
        )
        self.assertEqual(within["status"], "present")
        self.assertEqual(within["late_minutes"], 0)
        late = evaluate_times(
            day=day,
            tz_name="Asia/Karachi",
            shift_start=time(9, 0),
            shift_end=time(17, 0),
            overnight=False,
            break_minutes=60,
            grace_minutes=10,
            early_grace_minutes=10,
            half_day_threshold_minutes=240,
            check_in=punch(day, 9, 11),
            check_out=punch(day, 17, 0),
            is_weekly_off=False,
            is_holiday=False,
            has_leave=False,
        )
        self.assertEqual(late["status"], "late")
        self.assertEqual(late["late_minutes"], 11)

    def test_overnight_shift_and_early_departure(self):
        day = datetime(2026, 10, 5).date()
        result = evaluate_times(
            day=day,
            tz_name="Asia/Karachi",
            shift_start=time(22, 0),
            shift_end=time(6, 0),
            overnight=True,
            break_minutes=60,
            grace_minutes=10,
            early_grace_minutes=10,
            half_day_threshold_minutes=240,
            check_in=punch(day, 22, 20),
            check_out=punch(day + __import__("datetime").timedelta(days=1), 5, 0),
            is_weekly_off=False,
            is_holiday=False,
            has_leave=False,
        )
        self.assertTrue(result["shift_overnight"])
        self.assertEqual(result["late_minutes"], 20)
        self.assertEqual(result["status"], "late")
        self.assertEqual(result["early_departure_minutes"], 60)
        self.assertEqual(result["working_minutes"], 340)

    def test_missing_checkout_is_incomplete_not_absent(self):
        day = datetime(2026, 10, 8).date()
        result = evaluate_times(
            day=day,
            tz_name="Asia/Karachi",
            shift_start=time(9, 0),
            shift_end=time(17, 0),
            overnight=False,
            break_minutes=60,
            grace_minutes=10,
            early_grace_minutes=10,
            half_day_threshold_minutes=240,
            check_in=punch(day, 9, 0),
            check_out=None,
            is_weekly_off=False,
            is_holiday=False,
            has_leave=False,
        )
        self.assertEqual(result["status"], "incomplete")
        self.assertTrue(result["is_incomplete"])

    def test_checkout_before_checkin_is_rejected(self):
        day = datetime(2026, 10, 8).date()
        with self.assertRaises(TimeError):
            evaluate_times(
                day=day,
                tz_name="Asia/Karachi",
                shift_start=time(9, 0),
                shift_end=time(17, 0),
                overnight=False,
                break_minutes=0,
                grace_minutes=0,
                early_grace_minutes=0,
                half_day_threshold_minutes=0,
                check_in=punch(day, 10, 0),
                check_out=punch(day, 9, 0),
                is_weekly_off=False,
                is_holiday=False,
                has_leave=False,
            )

    def test_weekly_off_without_a_punch_is_not_absent(self):
        day = datetime(2026, 10, 4).date()
        result = evaluate_times(
            day=day,
            tz_name="Asia/Karachi",
            shift_start=time(9, 0),
            shift_end=time(17, 0),
            overnight=False,
            break_minutes=60,
            grace_minutes=10,
            early_grace_minutes=10,
            half_day_threshold_minutes=240,
            check_in=None,
            check_out=None,
            is_weekly_off=True,
            is_holiday=False,
            has_leave=False,
            today=day + __import__("datetime").timedelta(days=1),
        )
        self.assertEqual(result["status"], "weekly_off")
