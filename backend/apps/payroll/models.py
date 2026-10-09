from django.conf import settings
from django.db import models
from django.db.models import Q


class PayrollPeriod(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CALCULATED = "calculated", "Calculated"
        APPROVED = "approved", "Approved"
        FINALIZED = "finalized", "Finalized"
        REOPENED = "reopened", "Reopened"

    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    divisor_mode = models.CharField(max_length=40, blank=True)
    policy_fingerprint = models.CharField(max_length=64, blank=True)
    needs_recalculation = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    calculated_at = models.DateTimeField(null=True, blank=True)
    calculated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="payroll_calculations"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="payroll_approvals"
    )
    finalized_at = models.DateTimeField(null=True, blank=True)
    finalized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="payroll_finalizations"
    )
    reopen_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-year", "-month"]
        constraints = [
            models.UniqueConstraint(fields=["year", "month"], name="uniq_payroll_period"),
            models.CheckConstraint(condition=Q(month__gte=1) & Q(month__lte=12), name="payroll_month_range"),
        ]

    def __str__(self):
        return f"{self.year}-{self.month:02d} ({self.status})"


class PayrollRecord(models.Model):
    class PaymentStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        UNPAID = "unpaid", "Unpaid"
        PARTIALLY_PAID = "partially_paid", "Partially paid"
        PAID = "paid", "Paid"

    period = models.ForeignKey(PayrollPeriod, on_delete=models.PROTECT, related_name="records")
    employee = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="payroll_records")
    salary_type = models.CharField(max_length=20)
    scheduled_working_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    present_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    absent_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    half_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    paid_leave_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    unpaid_leave_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    weekly_offs = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    public_holidays = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    late_count = models.PositiveIntegerField(default=0)
    late_minutes = models.PositiveIntegerField(default=0)
    early_departures = models.PositiveIntegerField(default=0)
    working_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    overtime_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    attendance_percentage = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    allowances_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bonuses_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overtime_pay = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gross_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    approved_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unpaid_leave_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    attendance_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    late_penalty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    advances_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_adjustments = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_date = models.DateField(null=True, blank=True)
    payment_method = models.CharField(max_length=40, blank=True)
    payment_reference = models.CharField(max_length=80, blank=True)
    notes = models.TextField(blank=True)
    breakdown = models.JSONField(default=dict, blank=True)
    advances_applied = models.BooleanField(default=False)
    calculated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["employee__employee_code"]
        constraints = [
            models.UniqueConstraint(fields=["period", "employee"], name="uniq_payroll_employee_period"),
        ]
        indexes = [models.Index(fields=["payment_status"])]

    def __str__(self):
        return f"{self.employee.employee_code} {self.period}"


class PayrollLineItem(models.Model):
    class Kind(models.TextChoices):
        EARNING = "earning", "Earning"
        DEDUCTION = "deduction", "Deduction"

    record = models.ForeignKey(PayrollRecord, on_delete=models.CASCADE, related_name="line_items")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    code = models.CharField(max_length=64)
    label = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    is_manual = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    reason = models.TextField(blank=True)

    class Meta:
        ordering = ["kind", "code", "id"]


class SalaryPayment(models.Model):
    record = models.ForeignKey(PayrollRecord, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_on = models.DateField()
    method = models.CharField(max_length=40)
    reference = models.CharField(max_length=80, blank=True)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-paid_on", "-id"]
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0), name="payment_positive")]


class SalaryAdvance(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        RECOVERED = "recovered", "Recovered"
        CANCELLED = "cancelled", "Cancelled"

    employee = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="advances")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    remaining = models.DecimalField(max_digits=12, decimal_places=2)
    issued_date = models.DateField()
    monthly_recovery = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issued_date"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="advance_positive"),
            models.CheckConstraint(condition=Q(remaining__gte=0), name="advance_remaining_nonnegative"),
        ]


class Bonus(models.Model):
    employee = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="bonuses")
    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField()
    label = models.CharField(max_length=120, default="Bonus")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-year", "-month"]
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0), name="bonus_positive")]


class Deduction(models.Model):
    employee = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="deductions")
    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField()
    label = models.CharField(max_length=120)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-year", "-month"]
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0), name="deduction_positive")]


class AdvanceRecovery(models.Model):
    payroll_record = models.ForeignKey(PayrollRecord, on_delete=models.CASCADE, related_name="advance_recoveries")
    advance = models.ForeignKey(SalaryAdvance, on_delete=models.PROTECT, related_name="recoveries")
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["payroll_record", "advance"], name="uniq_advance_recovery"),
        ]
