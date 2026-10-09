from django.conf import settings
from django.db import models
from django.db.models import Q


class Employee(models.Model):
    class EmploymentType(models.TextChoices):
        FULL_TIME = "full_time", "Full time"
        PART_TIME = "part_time", "Part time"
        CONTRACT = "contract", "Contract"
        INTERN = "intern", "Intern"
        DAILY_WAGE = "daily_wage", "Daily wage"
        HOURLY = "hourly", "Hourly"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        ON_NOTICE = "on_notice", "On notice"
        TERMINATED = "terminated", "Terminated"

    class SalaryType(models.TextChoices):
        MONTHLY = "monthly", "Fixed monthly"
        DAILY = "daily", "Daily wage"
        HOURLY = "hourly", "Hourly wage"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="employee_profile",
    )
    employee_code = models.CharField(max_length=32, unique=True)
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    photo = models.ImageField(upload_to="employees/", blank=True, null=True)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    emergency_contact_name = models.CharField(max_length=120, blank=True)
    emergency_contact_phone = models.CharField(max_length=32, blank=True)
    emergency_contact_relation = models.CharField(max_length=60, blank=True)
    department = models.ForeignKey("organization.Department", null=True, blank=True, on_delete=models.PROTECT, related_name="employees")
    job_title = models.ForeignKey("organization.JobTitle", null=True, blank=True, on_delete=models.PROTECT, related_name="employees")
    location = models.ForeignKey("organization.OfficeLocation", null=True, blank=True, on_delete=models.SET_NULL, related_name="employees")
    employment_type = models.CharField(max_length=20, choices=EmploymentType.choices, default=EmploymentType.FULL_TIME)
    joining_date = models.DateField()
    exit_date = models.DateField(null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    shift = models.ForeignKey("organization.Shift", null=True, blank=True, on_delete=models.SET_NULL, related_name="employees")
    weekly_off_days = models.JSONField(null=True, blank=True)
    salary_type = models.CharField(max_length=20, choices=SalaryType.choices, default=SalaryType.MONTHLY)
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    daily_rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    hourly_rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bank_name = models.CharField(max_length=120, blank=True)
    bank_account_name = models.CharField(max_length=120, blank=True)
    bank_account_number = models.CharField(max_length=64, blank=True)
    bank_routing = models.CharField(max_length=64, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["employee_code"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["department", "status"]),
            models.Index(fields=["joining_date"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["email"], condition=~Q(email=""), name="uniq_employee_email_present"),
            models.CheckConstraint(condition=Q(basic_salary__gte=0), name="employee_basic_nonnegative"),
            models.CheckConstraint(condition=Q(daily_rate__gte=0), name="employee_daily_nonnegative"),
            models.CheckConstraint(condition=Q(hourly_rate__gte=0), name="employee_hourly_nonnegative"),
        ]

    def __str__(self):
        return f"{self.employee_code} {self.full_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class EmployeeAllowance(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="allowances")
    name = models.CharField(max_length=120)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gte=0), name="allowance_nonnegative"),
        ]

    def __str__(self):
        return f"{self.name} ({self.employee.employee_code})"


class EmploymentEvent(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=40)
    summary = models.CharField(max_length=255)
    from_value = models.CharField(max_length=255, blank=True)
    to_value = models.CharField(max_length=255, blank=True)
    reason = models.TextField(blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.summary
