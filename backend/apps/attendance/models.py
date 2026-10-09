from django.conf import settings
from django.db import models


class AttendanceRecord(models.Model):
    class Status(models.TextChoices):
        PRESENT = "present", "Present"
        LATE = "late", "Late"
        ABSENT = "absent", "Absent"
        HALF_DAY = "half_day", "Half-day"
        ON_LEAVE = "on_leave", "On leave"
        WEEKLY_OFF = "weekly_off", "Weekly off"
        PUBLIC_HOLIDAY = "public_holiday", "Public holiday"
        HOLIDAY_WORKED = "holiday_worked", "Holiday worked"
        OFF_WORKED = "off_worked", "Weekly off worked"
        INCOMPLETE = "incomplete", "Incomplete attendance"

    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        SELF = "self", "Employee check-in"
        IMPORT = "import", "Excel import"
        SYSTEM = "system", "System"
        CORRECTION = "correction", "Correction"

    employee = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="attendance_records")
    date = models.DateField()
    shift_slot = models.PositiveSmallIntegerField(default=1)
    shift = models.ForeignKey("organization.Shift", null=True, blank=True, on_delete=models.SET_NULL)
    shift_start = models.TimeField(null=True, blank=True)
    shift_end = models.TimeField(null=True, blank=True)
    shift_overnight = models.BooleanField(default=False)
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    break_minutes = models.PositiveIntegerField(default=0)
    scheduled_minutes = models.PositiveIntegerField(default=0)
    working_minutes = models.PositiveIntegerField(default=0)
    late_minutes = models.PositiveIntegerField(default=0)
    early_departure_minutes = models.PositiveIntegerField(default=0)
    overtime_minutes = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=32, choices=Status.choices)
    notes = models.TextField(blank=True)
    source = models.CharField(max_length=32, choices=Source.choices, default=Source.MANUAL)
    is_incomplete = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="attendance_created"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="attendance_updated"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "employee_id", "shift_slot"]
        constraints = [
            models.UniqueConstraint(fields=["employee", "date", "shift_slot"], name="uniq_attendance_employee_date_slot"),
        ]
        indexes = [
            models.Index(fields=["date", "status"]),
            models.Index(fields=["employee", "date"]),
        ]

    def __str__(self):
        return f"{self.employee.employee_code} {self.date} {self.status}"


class AttendanceAdjustment(models.Model):
    attendance = models.ForeignKey(AttendanceRecord, on_delete=models.CASCADE, related_name="adjustments")
    previous_data = models.JSONField(default=dict)
    new_data = models.JSONField(default=dict)
    reason = models.TextField()
    adjusted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Adjustment {self.attendance_id} at {self.created_at}"
