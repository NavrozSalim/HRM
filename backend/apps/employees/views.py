from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.common.audit import audit
from apps.common.exceptions import BusinessError
from apps.common.permissions import IsHROrSuper
from apps.employees.models import Employee, EmployeeAllowance
from apps.employees.serializers import AllowanceSerializer, DeactivateSerializer, EmployeeSerializer, EmploymentEventSerializer
from apps.employees.services import can_view_salary, money_changed, next_employee_code, record_event, visible_employees
from apps.leaves.services import ensure_balances

User = get_user_model()


class EmployeeViewSet(viewsets.ModelViewSet):
    serializer_class = EmployeeSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    search_fields = ["first_name", "last_name", "employee_code", "email", "phone"]
    ordering_fields = ["employee_code", "first_name", "last_name", "joining_date", "status"]
    filterset_fields = ["department", "status", "employment_type", "salary_type", "shift", "location"]

    def get_queryset(self):
        return visible_employees(self.request.user)

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy", "deactivate", "reactivate"}:
            return [IsHROrSuper()]
        return super().get_permissions()

    @transaction.atomic
    def perform_create(self, serializer):
        account = serializer.validated_data.pop("create_account", False)
        username = serializer.validated_data.pop("account_username", "")
        password = serializer.validated_data.pop("account_password", "")
        if not serializer.validated_data.get("employee_code"):
            serializer.validated_data["employee_code"] = next_employee_code()
        employee = serializer.save()
        if account:
            if not username or not password:
                raise BusinessError("Username and password are required to create a login.")
            user = User(username=username, email=employee.email, first_name=employee.first_name, last_name=employee.last_name, role=User.Role.EMPLOYEE)
            user.set_password(password)
            user.save()
            employee.user = user
            employee.save(update_fields=["user"])
        ensure_balances(employee, employee.joining_date.year)
        record_event(employee=employee, event_type="hired", summary=f"{employee.full_name} joined.", actor=self.request.user, to_value=employee.status)
        audit(actor=self.request.user, action="employee.create", instance=employee, summary=f"Added employee {employee.full_name}.", request=self.request)

    @transaction.atomic
    def perform_update(self, serializer):
        before = Employee.objects.get(pk=serializer.instance.pk)
        serializer.validated_data.pop("create_account", None)
        serializer.validated_data.pop("account_username", None)
        serializer.validated_data.pop("account_password", None)
        employee = serializer.save()
        actor = self.request.user
        if before.status != employee.status:
            record_event(employee=employee, event_type="status_change", summary=f"Status changed from {before.status} to {employee.status}.", actor=actor, from_value=before.status, to_value=employee.status)
        if before.department_id != employee.department_id:
            record_event(employee=employee, event_type="transfer", summary="Department changed.", actor=actor, from_value=str(before.department or ""), to_value=str(employee.department or ""))
        if before.shift_id != employee.shift_id:
            record_event(employee=employee, event_type="shift_change", summary="Shift changed.", actor=actor, from_value=str(before.shift or ""), to_value=str(employee.shift or ""))
        if money_changed(before.basic_salary, employee.basic_salary) or before.salary_type != employee.salary_type:
            record_event(employee=employee, event_type="salary_change", summary="Salary structure changed.", actor=actor, from_value=f"{before.salary_type} {before.basic_salary}", to_value=f"{employee.salary_type} {employee.basic_salary}")
        audit(actor=actor, action="employee.update", instance=employee, summary=f"Updated employee {employee.full_name}.", request=self.request)

    def destroy(self, request, *args, **kwargs):
        raise BusinessError("Employees are not deleted. Deactivate the profile so attendance and payroll history stay intact.")

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        employee = self.get_object()
        serializer = DeactivateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if len(serializer.validated_data["reason"].strip()) < 3:
            raise BusinessError("Enter a reason for deactivation.")
        employee.status = Employee.Status.INACTIVE
        employee.exit_date = serializer.validated_data["exit_date"]
        employee.save(update_fields=["status", "exit_date", "updated_at"])
        if serializer.validated_data["disable_login"] and employee.user_id:
            employee.user.is_active = False
            employee.user.save(update_fields=["is_active"])
        record_event(employee=employee, event_type="status_change", summary="Employee deactivated.", actor=request.user, from_value="active", to_value="inactive", reason=serializer.validated_data["reason"])
        audit(actor=request.user, action="employee.deactivate", instance=employee, summary=f"Deactivated {employee.full_name}.", reason=serializer.validated_data["reason"], request=request)
        return Response(EmployeeSerializer(employee, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def reactivate(self, request, pk=None):
        employee = self.get_object()
        employee.status = Employee.Status.ACTIVE
        employee.exit_date = None
        employee.save(update_fields=["status", "exit_date", "updated_at"])
        if employee.user_id:
            employee.user.is_active = True
            employee.user.save(update_fields=["is_active"])
        record_event(employee=employee, event_type="status_change", summary="Employee reactivated.", actor=request.user, to_value="active", reason=request.data.get("reason", ""))
        audit(actor=request.user, action="employee.reactivate", instance=employee, summary=f"Reactivated {employee.full_name}.", request=request)
        return Response(EmployeeSerializer(employee, context={"request": request}).data)

    @action(detail=True, methods=["get"])
    def timeline(self, request, pk=None):
        employee = self.get_object()
        return Response(EmploymentEventSerializer(employee.events.all(), many=True).data)


class AllowanceViewSet(viewsets.ModelViewSet):
    serializer_class = AllowanceSerializer
    filterset_fields = ["employee", "is_active"]

    def get_queryset(self):
        qs = EmployeeAllowance.objects.select_related("employee")
        visible = visible_employees(self.request.user)
        qs = qs.filter(employee__in=visible)
        if self.request.user.role not in {"super_admin", "management", "hr_manager", "accountant"}:
            qs = qs.filter(employee__user=self.request.user)
        return qs

    def get_permissions(self):
        if self.request.method not in ("GET", "HEAD", "OPTIONS"):
            return [IsHROrSuper()]
        return super().get_permissions()

    def perform_create(self, serializer):
        employee = serializer.validated_data["employee"]
        if not visible_employees(self.request.user).filter(pk=employee.pk).exists():
            raise BusinessError("You cannot add an allowance for this employee.", status_code=403)
        if not can_view_salary(self.request.user, employee):
            raise BusinessError("You cannot change salary components for this employee.", status_code=403)
        allowance = serializer.save()
        from apps.payroll.services import mark_period_stale
        from datetime import date

        today = date.today()
        mark_period_stale(today.year, today.month)
        audit(actor=self.request.user, action="allowance.create", instance=allowance, summary=f"Added allowance {allowance.name} for {employee.full_name}.", request=self.request)
