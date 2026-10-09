from rest_framework import serializers

from apps.leaves.models import LeaveBalance, LeaveRequest, LeaveType


class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = [
            "id", "name", "code", "is_paid", "tracks_balance", "annual_entitlement", "allow_negative",
            "color", "requires_document", "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate_code(self, value):
        return value.strip().upper()

    def validate_annual_entitlement(self, value):
        if value < 0:
            raise serializers.ValidationError("Entitlement cannot be negative.")
        return value


class LeaveBalanceSerializer(serializers.ModelSerializer):
    leave_type_name = serializers.CharField(source="leave_type.name", read_only=True)
    leave_type_code = serializers.CharField(source="leave_type.code", read_only=True)
    is_paid = serializers.BooleanField(source="leave_type.is_paid", read_only=True)
    available = serializers.DecimalField(max_digits=6, decimal_places=2, read_only=True)
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    employee_code = serializers.CharField(source="employee.employee_code", read_only=True)

    class Meta:
        model = LeaveBalance
        fields = [
            "id", "employee", "employee_name", "employee_code", "leave_type", "leave_type_name", "leave_type_code",
            "is_paid", "year", "entitled", "used", "pending", "available", "updated_at",
        ]


class LeaveRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    employee_code = serializers.CharField(source="employee.employee_code", read_only=True)
    leave_type_name = serializers.CharField(source="leave_type.name", read_only=True)
    leave_type_code = serializers.CharField(source="leave_type.code", read_only=True)
    is_paid = serializers.BooleanField(source="leave_type.is_paid", read_only=True)
    reviewed_by_name = serializers.CharField(source="reviewed_by.display_name", read_only=True)
    document_url = serializers.SerializerMethodField()

    class Meta:
        model = LeaveRequest
        fields = [
            "id", "employee", "employee_name", "employee_code", "leave_type", "leave_type_name", "leave_type_code",
            "is_paid", "start_date", "end_date", "day_part", "total_days", "reason", "document", "document_url",
            "status", "review_note", "reviewed_by", "reviewed_by_name", "reviewed_at", "created_at", "updated_at",
        ]
        read_only_fields = ["total_days", "status", "review_note", "reviewed_by", "reviewed_at", "created_at", "updated_at"]

    def get_document_url(self, obj):
        request = self.context.get("request")
        if obj.document and request:
            return request.build_absolute_uri(obj.document.url)
        return None

    def validate_document(self, value):
        if value and value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Supporting documents must be 5 MB or smaller.")
        return value
