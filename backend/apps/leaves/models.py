from django.conf import settings
from django.db import models
from django.db.models import Q


class LeaveType(models.Model):
    name = models.CharField(max_length=80, unique=True)
    code = models.CharField(max_length=20, unique=True)
    is_paid = models.BooleanField(default=True)
    tracks_balance = models.BooleanField(default=True)
    annual_entitlement = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    allow_negative = models.BooleanField(default=False)
    color = models.CharField(max_length=20, default="#0f766e")
    requires_document = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class LeaveBalance(models.Model):
    employee = models.ForeignKey("employees.Employee", on_delete=models.CASCADE, related_name="leave_balances")
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE, related_name="balances")
    year = models.PositiveIntegerField()
    entitled = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    used = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    pending = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["employee", "leave_type", "year"], name="uniq_leave_balance"),
            models.CheckConstraint(condition=Q(entitled__gte=0), name="leave_entitled_nonnegative"),
            models.CheckConstraint(condition=Q(used__gte=0), name="leave_used_nonnegative"),
            models.CheckConstraint(condition=Q(pending__gte=0), name="leave_pending_nonnegative"),
        ]
        ordering = ["leave_type__name"]

    @property
    def available(self):
        return self.entitled - self.used - self.pending


class LeaveRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    class DayPart(models.TextChoices):
        FULL = "full", "Full day"
        FIRST = "first_half", "First half"
        SECOND = "second_half", "Second half"

    employee = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="leave_requests")
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT, related_name="requests")
    start_date = models.DateField()
    end_date = models.DateField()
    day_part = models.CharField(max_length=20, choices=DayPart.choices, default=DayPart.FULL)
    total_days = models.DecimalField(max_digits=6, decimal_places=2)
    reason = models.TextField()
    document = models.FileField(upload_to="leave-documents/", blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    review_note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="leave_reviews"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "start_date"]),
            models.Index(fields=["employee", "start_date"]),
        ]

    def __str__(self):
        return f"{self.employee.employee_code} {self.leave_type.code} {self.start_date}"
