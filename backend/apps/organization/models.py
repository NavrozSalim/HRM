from decimal import Decimal

from django.conf import settings
from django.db import models


def default_weekly_offs():
    return [5, 6]


class OfficeLocation(models.Model):
    name = models.CharField(max_length=120, unique=True)
    address = models.TextField(blank=True)
    timezone = models.CharField(max_length=64, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Department(models.Model):
    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="managed_departments",
    )
    location = models.ForeignKey(OfficeLocation, null=True, blank=True, on_delete=models.SET_NULL, related_name="departments")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class JobTitle(models.Model):
    name = models.CharField(max_length=120)
    department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.CASCADE, related_name="job_titles")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["name", "department"], name="uniq_job_title_department"),
        ]

    def __str__(self):
        return self.name


class Shift(models.Model):
    name = models.CharField(max_length=120, unique=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    break_minutes = models.PositiveIntegerField(default=60)
    grace_minutes = models.PositiveIntegerField(default=10)
    early_grace_minutes = models.PositiveIntegerField(default=10)
    is_overnight = models.BooleanField(default=False)
    timezone = models.CharField(max_length=64, blank=True)
    weekly_off_days = models.JSONField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        self.is_overnight = self.end_time <= self.start_time
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Holiday(models.Model):
    name = models.CharField(max_length=160)
    date = models.DateField()
    location = models.ForeignKey(OfficeLocation, null=True, blank=True, on_delete=models.CASCADE, related_name="holidays")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date", "name"]
        indexes = [models.Index(fields=["date"])]

    def __str__(self):
        return f"{self.name} ({self.date})"


class OfficeSettings(models.Model):
    class DivisorMode(models.TextChoices):
        CALENDAR = "calendar_days", "Calendar days"
        SCHEDULED = "scheduled_working_days", "Scheduled working days"
        FIXED = "fixed", "Fixed divisor"

    class PenaltyMode(models.TextChoices):
        PER_OCCURRENCE = "per_occurrence", "Per late arrival"
        PER_MINUTE = "per_minute", "Per late minute"

    company_name = models.CharField(max_length=200, default="Wesolucions")
    legal_name = models.CharField(max_length=200, blank=True)
    timezone = models.CharField(max_length=64, default="Asia/Karachi")
    currency = models.CharField(max_length=8, default="USD")
    standard_work_minutes = models.PositiveIntegerField(default=480)
    default_grace_minutes = models.PositiveIntegerField(default=10)
    early_departure_grace_minutes = models.PositiveIntegerField(default=10)
    half_day_threshold_minutes = models.PositiveIntegerField(default=240)
    monthly_late_warning_threshold = models.PositiveIntegerField(default=3)
    overtime_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("1.50"))
    holiday_work_counts_as_overtime = models.BooleanField(default=True)
    salary_divisor_mode = models.CharField(max_length=40, choices=DivisorMode.choices, default=DivisorMode.SCHEDULED)
    fixed_salary_divisor = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("30"))
    unpaid_leave_deduction_enabled = models.BooleanField(default=True)
    absence_deduction_enabled = models.BooleanField(default=False)
    late_penalty_enabled = models.BooleanField(default=False)
    late_penalty_mode = models.CharField(max_length=32, choices=PenaltyMode.choices, default=PenaltyMode.PER_OCCURRENCE)
    late_penalty_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    daily_wage_pays_weekly_off = models.BooleanField(default=False)
    daily_wage_pays_holiday = models.BooleanField(default=False)
    daily_wage_pays_paid_leave = models.BooleanField(default=True)
    self_checkin_enabled = models.BooleanField(default=True)
    biometric_enabled = models.BooleanField(default=False)
    default_weekly_off_days = models.JSONField(default=default_weekly_offs)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Office settings"
        verbose_name_plural = "Office settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return self.company_name
