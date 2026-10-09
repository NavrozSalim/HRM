from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from rest_framework import serializers

from apps.common.exceptions import BusinessError
from apps.employees.services import validate_weekdays
from apps.organization.models import Department, Holiday, JobTitle, OfficeLocation, OfficeSettings, Shift


class OfficeLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfficeLocation
        fields = ["id", "name", "address", "timezone", "is_active", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]

    def validate_timezone(self, value):
        if value:
            _check_timezone(value)
        return value


class DepartmentSerializer(serializers.ModelSerializer):
    manager_name = serializers.CharField(source="manager.display_name", read_only=True)
    location_name = serializers.CharField(source="location.name", read_only=True)

    class Meta:
        model = Department
        fields = ["id", "name", "code", "description", "manager", "manager_name", "location", "location_name", "is_active", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]

    def validate_code(self, value):
        return value.strip().upper()


class JobTitleSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = JobTitle
        fields = ["id", "name", "department", "department_name", "is_active", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]


class ShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shift
        fields = [
            "id", "name", "start_time", "end_time", "break_minutes", "grace_minutes", "early_grace_minutes",
            "is_overnight", "timezone", "weekly_off_days", "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["is_overnight", "created_at", "updated_at"]

    def validate_timezone(self, value):
        if value:
            _check_timezone(value)
        return value

    def validate_weekly_off_days(self, value):
        if value is None:
            return None
        return validate_weekdays(value)

    def validate(self, attrs):
        for field in ("break_minutes", "grace_minutes", "early_grace_minutes"):
            if attrs.get(field, 0) < 0:
                raise serializers.ValidationError({field: "This value cannot be negative."})
        return attrs


class HolidaySerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.name", read_only=True)

    class Meta:
        model = Holiday
        fields = ["id", "name", "date", "location", "location_name", "is_active", "notes", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, attrs):
        date = attrs.get("date", getattr(self.instance, "date", None))
        location = attrs.get("location", getattr(self.instance, "location", None))
        qs = Holiday.objects.filter(date=date, location=location)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A holiday already exists for that date and location.")
        return attrs


class OfficeSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfficeSettings
        fields = [
            "company_name", "legal_name", "timezone", "currency", "standard_work_minutes", "default_grace_minutes",
            "early_departure_grace_minutes", "half_day_threshold_minutes", "monthly_late_warning_threshold",
            "overtime_multiplier", "holiday_work_counts_as_overtime", "salary_divisor_mode", "fixed_salary_divisor",
            "unpaid_leave_deduction_enabled", "absence_deduction_enabled", "late_penalty_enabled", "late_penalty_mode",
            "late_penalty_amount", "daily_wage_pays_weekly_off", "daily_wage_pays_holiday", "daily_wage_pays_paid_leave",
            "self_checkin_enabled", "biometric_enabled", "default_weekly_off_days", "updated_at",
        ]
        read_only_fields = ["updated_at"]

    def validate_timezone(self, value):
        _check_timezone(value)
        return value

    def validate_default_weekly_off_days(self, value):
        return validate_weekdays(value)

    def validate_fixed_salary_divisor(self, value):
        if value <= 0:
            raise serializers.ValidationError("The salary divisor must be greater than zero.")
        return value

    def validate(self, attrs):
        for field in ("standard_work_minutes", "default_grace_minutes", "early_departure_grace_minutes", "half_day_threshold_minutes", "late_penalty_amount", "overtime_multiplier"):
            if field in attrs and attrs[field] < 0:
                raise serializers.ValidationError({field: "This value cannot be negative."})
        return attrs


def _check_timezone(value):
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise BusinessError(f"{value} is not a recognized time zone.") from exc
