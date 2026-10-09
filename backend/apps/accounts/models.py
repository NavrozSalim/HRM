from django.contrib.auth.models import AbstractUser, UserManager as DjangoUserManager
from django.db import models


class UserManager(DjangoUserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", User.Role.SUPER_ADMIN)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        SUPER_ADMIN = "super_admin", "Super user"
        MANAGEMENT = "management", "Management"
        EMPLOYEE = "employee", "Employee"
        # Kept so older records and tests still load. The app no longer offers these.
        HR_MANAGER = "hr_manager", "HR Manager"
        ACCOUNTANT = "accountant", "Accountant"
        DEPARTMENT_MANAGER = "department_manager", "Department Manager"

    role = models.CharField(max_length=32, choices=Role.choices, default=Role.EMPLOYEE)
    phone = models.CharField(max_length=32, blank=True)
    objects = UserManager()

    class Meta:
        indexes = [models.Index(fields=["role"])]

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def display_name(self):
        return self.get_full_name() or self.username
