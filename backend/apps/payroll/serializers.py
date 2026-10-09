from rest_framework import serializers

from apps.payroll.models import Bonus, Deduction, PayrollPeriod, PayrollRecord, SalaryAdvance, SalaryPayment


class PayrollPeriodSerializer(serializers.ModelSerializer):
    total_net = serializers.SerializerMethodField()
    employee_count = serializers.SerializerMethodField()
    total_unpaid = serializers.SerializerMethodField()

    class Meta:
        model = PayrollPeriod
        fields = [
            "id", "year", "month", "status", "divisor_mode", "needs_recalculation", "notes",
            "calculated_at", "approved_at", "finalized_at", "reopen_reason", "employee_count",
            "total_net", "total_unpaid", "created_at", "updated_at",
        ]
        read_only_fields = ["status", "divisor_mode", "needs_recalculation", "calculated_at", "approved_at", "finalized_at", "reopen_reason"]

    def get_total_net(self, obj):
        if not self.context.get("show_money", True):
            return None
        return format(sum((record.net_salary for record in obj.records.all()), 0), "f") if obj.records.all() else "0.00"

    def get_employee_count(self, obj):
        return obj.records.count()

    def get_total_unpaid(self, obj):
        if not self.context.get("show_money", True):
            return None
        total = 0
        for record in obj.records.all():
            if record.payment_status in {"unpaid", "partially_paid", "pending"} and obj.status == "finalized":
                total += record.net_salary - record.amount_paid
        return format(total, "f")


class PayrollRecordSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    employee_code = serializers.CharField(source="employee.employee_code", read_only=True)
    department = serializers.CharField(source="employee.department.name", read_only=True)
    period_label = serializers.SerializerMethodField()
    lines = serializers.SerializerMethodField()

    class Meta:
        model = PayrollRecord
        fields = [
            "id", "period", "period_label", "employee", "employee_name", "employee_code", "department", "salary_type",
            "scheduled_working_days", "present_days", "absent_days", "half_days", "paid_leave_days",
            "unpaid_leave_days", "weekly_offs", "public_holidays", "late_count", "late_minutes",
            "early_departures", "working_hours", "overtime_hours", "attendance_percentage", "basic_salary",
            "allowances_total", "bonuses_total", "overtime_pay", "gross_salary", "approved_deductions",
            "unpaid_leave_deduction", "attendance_deduction", "late_penalty", "advances_total",
            "other_adjustments", "total_deductions", "net_salary", "payment_status", "amount_paid",
            "payment_date", "payment_method", "payment_reference", "notes", "breakdown", "lines", "calculated_at",
        ]

    def get_period_label(self, obj):
        return f"{obj.period.year}-{obj.period.month:02d}"

    def get_lines(self, obj):
        return [
            {"id": item.id, "kind": item.kind, "code": item.code, "label": item.label, "amount": format(item.amount, "f"), "manual": item.is_manual, "reason": item.reason}
            for item in obj.line_items.all()
        ]


class SalaryAdvanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)

    class Meta:
        model = SalaryAdvance
        fields = ["id", "employee", "employee_name", "amount", "remaining", "issued_date", "monthly_recovery", "reason", "status", "created_at"]
        read_only_fields = ["remaining", "status", "created_at"]


class BonusSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)

    class Meta:
        model = Bonus
        fields = ["id", "employee", "employee_name", "year", "month", "label", "amount", "reason", "created_at"]
        read_only_fields = ["created_at"]


class DeductionSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)

    class Meta:
        model = Deduction
        fields = ["id", "employee", "employee_name", "year", "month", "label", "amount", "reason", "created_at"]
        read_only_fields = ["created_at"]


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalaryPayment
        fields = ["id", "amount", "paid_on", "method", "reference", "notes", "created_at"]
