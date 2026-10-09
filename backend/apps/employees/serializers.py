import re

from rest_framework import serializers

from apps.employees.models import Employee, EmployeeAllowance, EmploymentEvent
from apps.employees.services import SALARY_FIELDS, can_view_salary, validate_weekdays

PHONE_RE = re.compile(r"^[0-9+\-\s()]{7,20}$")


class AllowanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeAllowance
        fields = ["id", "employee", "name", "amount", "is_active", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]

    def validate_amount(self, value):
        if value < 0:
            raise serializers.ValidationError("Allowance cannot be negative.")
        return value


class EmployeeSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    photo_url = serializers.SerializerMethodField()
    department_name = serializers.CharField(source="department.name", read_only=True)
    job_title_name = serializers.CharField(source="job_title.name", read_only=True)
    shift_name = serializers.CharField(source="shift.name", read_only=True)
    location_name = serializers.CharField(source="location.name", read_only=True)
    create_account = serializers.BooleanField(write_only=True, required=False, default=False)
    account_username = serializers.CharField(write_only=True, required=False, allow_blank=True)
    account_password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Employee
        extra_kwargs = {"employee_code": {"required": False, "allow_blank": True}}
        fields = [
            "id", "user", "employee_code", "first_name", "last_name", "full_name", "photo", "photo_url",
            "phone", "email", "address", "emergency_contact_name", "emergency_contact_phone", "emergency_contact_relation",
            "department", "department_name", "job_title", "job_title_name", "location", "location_name",
            "employment_type", "joining_date", "exit_date", "date_of_birth", "status", "shift", "shift_name",
            "weekly_off_days", "salary_type", "basic_salary", "daily_rate", "hourly_rate", "bank_name",
            "bank_account_name", "bank_account_number", "bank_routing", "notes", "create_account",
            "account_username", "account_password", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "user"]

    def get_photo_url(self, obj):
        request = self.context.get("request")
        if obj.photo and request:
            return request.build_absolute_uri(obj.photo.url)
        return None

    def validate_phone(self, value):
        if value and not PHONE_RE.match(value):
            raise serializers.ValidationError("Enter a phone number using digits and + - ( ).")
        return value

    def validate_emergency_contact_phone(self, value):
        return self.validate_phone(value)

    def validate_weekly_off_days(self, value):
        if value is None:
            return None
        return validate_weekdays(value)

    def validate_photo(self, value):
        if value and value.size > 2 * 1024 * 1024:
            raise serializers.ValidationError("Profile photos must be 2 MB or smaller.")
        return value

    def validate(self, attrs):
        for field in ("basic_salary", "daily_rate", "hourly_rate"):
            if attrs.get(field, 0) < 0:
                raise serializers.ValidationError({field: "Amount cannot be negative."})
        joining = attrs.get("joining_date", getattr(self.instance, "joining_date", None))
        exit_date = attrs.get("exit_date", getattr(self.instance, "exit_date", None))
        if joining and exit_date and exit_date < joining:
            raise serializers.ValidationError({"exit_date": "Exit date cannot be before the joining date."})
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        if request and not can_view_salary(request.user, instance):
            for field in SALARY_FIELDS:
                data.pop(field, None)
        data.pop("photo", None)
        return data


class EmploymentEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.display_name", read_only=True)

    class Meta:
        model = EmploymentEvent
        fields = ["id", "event_type", "summary", "from_value", "to_value", "reason", "actor_name", "created_at"]


class DeactivateSerializer(serializers.Serializer):
    exit_date = serializers.DateField()
    reason = serializers.CharField()
    disable_login = serializers.BooleanField(required=False, default=True)
