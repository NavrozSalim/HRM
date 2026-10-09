from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.exceptions import BusinessError
from apps.common.permissions import CanManagePayroll, CanViewPayroll
from apps.employees.services import visible_employees
from apps.payroll.models import Bonus, Deduction, PayrollPeriod, PayrollRecord, SalaryAdvance
from apps.payroll.serializers import BonusSerializer, DeductionSerializer, PayrollPeriodSerializer, PayrollRecordSerializer, SalaryAdvanceSerializer
from apps.payroll.services import (
    adjust_record,
    approve_period,
    calculate_period,
    finalize_period,
    mark_period_stale,
    record_payment,
    reopen_period,
    slip_payload,
)


def _money_context(user):
    return {"show_money": user.role in {"super_admin", "management", "accountant", "hr_manager"}}


class PayrollPeriodViewSet(viewsets.ModelViewSet):
    serializer_class = PayrollPeriodSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]
    filterset_fields = ["year", "month", "status"]

    def get_queryset(self):
        if self.request.user.role == "employee":
            return PayrollPeriod.objects.filter(records__employee__user=self.request.user).distinct()
        if self.request.user.role == "department_manager":
            return PayrollPeriod.objects.none()
        return PayrollPeriod.objects.all()

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [CanViewPayroll()]
        return [CanManagePayroll()]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update(_money_context(self.request.user))
        return context

    def perform_create(self, serializer):
        year = serializer.validated_data["year"]
        month = serializer.validated_data["month"]
        if PayrollPeriod.objects.filter(year=year, month=month).exists():
            raise BusinessError("A payroll period for that month already exists.")
        serializer.save(status=PayrollPeriod.Status.OPEN)

    @action(detail=True, methods=["post"])
    def calculate(self, request, pk=None):
        period = calculate_period(period=self.get_object(), actor=request.user, request=request)
        return Response(self.get_serializer(period).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        period = approve_period(period=self.get_object(), actor=request.user, request=request)
        return Response(self.get_serializer(period).data)

    @action(detail=True, methods=["post"])
    def finalize(self, request, pk=None):
        period = finalize_period(period=self.get_object(), actor=request.user, request=request)
        return Response(self.get_serializer(period).data)

    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        period = reopen_period(period=self.get_object(), actor=request.user, reason=request.data.get("reason", ""), request=request)
        return Response(self.get_serializer(period).data)


class PayrollRecordViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PayrollRecordSerializer
    filterset_fields = ["period", "employee", "payment_status", "salary_type"]

    def get_queryset(self):
        qs = PayrollRecord.objects.filter(employee__in=visible_employees(self.request.user)).select_related("employee", "employee__department", "period").prefetch_related("line_items")
        if self.request.user.role == "department_manager":
            return qs.none()
        if self.request.user.role == "employee":
            return qs.filter(employee__user=self.request.user)
        return qs

    def get_permissions(self):
        if getattr(self, "action", None) in {"adjust", "pay"}:
            return [CanManagePayroll()]
        return [CanViewPayroll()]

    @action(detail=True, methods=["post"], permission_classes=[CanManagePayroll])
    def adjust(self, request, pk=None):
        record = adjust_record(
            record=self.get_object(),
            kind=request.data.get("kind"),
            label=request.data.get("label", "Manual adjustment"),
            amount=request.data.get("amount"),
            reason=request.data.get("reason", ""),
            actor=request.user,
            request=request,
        )
        return Response(PayrollRecordSerializer(record).data)

    @action(detail=True, methods=["post"], permission_classes=[CanManagePayroll])
    def pay(self, request, pk=None):
        from datetime import datetime

        paid_on = request.data.get("paid_on")
        try:
            paid_on = datetime.strptime(paid_on, "%Y-%m-%d").date()
        except (TypeError, ValueError) as exc:
            raise BusinessError("Payment date must use YYYY-MM-DD.") from exc
        payment = record_payment(
            record=self.get_object(),
            amount=request.data.get("amount"),
            paid_on=paid_on,
            method=request.data.get("method") or "bank",
            reference=request.data.get("reference", ""),
            notes=request.data.get("notes", ""),
            actor=request.user,
            request=request,
        )
        record = payment.record
        return Response({"payment_id": payment.id, "payment_status": record.payment_status, "amount_paid": format(record.amount_paid, "f")})

    @action(detail=True, methods=["get"])
    def slip(self, request, pk=None):
        record = self.get_object()
        payload = slip_payload(record)
        if request.query_params.get("format") == "pdf":
            from apps.insights.exports import pdf_response

            headers = ["Item", "Kind", "Amount"]
            rows = [[line["label"], line["kind"], line["amount"]] for line in payload["lines"]]
            rows.append(["Net salary", "", payload["net_salary"]])
            return pdf_response(
                f"salary-slip-{record.employee.employee_code}-{record.period.year}-{record.period.month:02d}.pdf",
                f"{payload['company']['name']} salary slip — {payload['employee']['full_name']} — {payload['period']['label']}",
                headers,
                rows,
            )
        return Response(payload)


class AdvanceViewSet(viewsets.ModelViewSet):
    serializer_class = SalaryAdvanceSerializer
    permission_classes = [CanManagePayroll]
    filterset_fields = ["employee", "status"]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return SalaryAdvance.objects.filter(employee__in=visible_employees(self.request.user)).select_related("employee")

    def perform_create(self, serializer):
        advance = serializer.save(remaining=serializer.validated_data["amount"], created_by=self.request.user)
        mark_period_stale(advance.issued_date.year, advance.issued_date.month)


class BonusViewSet(viewsets.ModelViewSet):
    serializer_class = BonusSerializer
    permission_classes = [CanManagePayroll]
    filterset_fields = ["employee", "year", "month"]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        return Bonus.objects.filter(employee__in=visible_employees(self.request.user)).select_related("employee")

    def perform_create(self, serializer):
        bonus = serializer.save(created_by=self.request.user)
        mark_period_stale(bonus.year, bonus.month)

    def perform_destroy(self, instance):
        mark_period_stale(instance.year, instance.month)
        instance.delete()


class DeductionViewSet(viewsets.ModelViewSet):
    serializer_class = DeductionSerializer
    permission_classes = [CanManagePayroll]
    filterset_fields = ["employee", "year", "month"]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        return Deduction.objects.filter(employee__in=visible_employees(self.request.user)).select_related("employee")

    def perform_create(self, serializer):
        item = serializer.save(created_by=self.request.user)
        mark_period_stale(item.year, item.month)

    def perform_destroy(self, instance):
        mark_period_stale(instance.year, instance.month)
        instance.delete()
