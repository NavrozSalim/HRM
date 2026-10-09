from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.common.permissions import IsHROrSuper, OrgWriteOrAuthenticatedRead
from apps.employees.services import visible_employees
from apps.leaves.models import LeaveBalance, LeaveRequest, LeaveType
from apps.leaves.serializers import LeaveBalanceSerializer, LeaveRequestSerializer, LeaveTypeSerializer
from apps.leaves.services import adjust_balance, cancel_leave, decide_leave, submit_leave


class LeaveTypeViewSet(viewsets.ModelViewSet):
    queryset = LeaveType.objects.all()
    serializer_class = LeaveTypeSerializer
    permission_classes = [OrgWriteOrAuthenticatedRead]
    search_fields = ["name", "code"]
    filterset_fields = ["is_active", "is_paid"]


class LeaveBalanceViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = LeaveBalanceSerializer
    filterset_fields = ["employee", "year", "leave_type"]

    def get_queryset(self):
        return LeaveBalance.objects.filter(employee__in=visible_employees(self.request.user)).select_related("employee", "leave_type")

    @action(detail=True, methods=["post"], permission_classes=[IsHROrSuper])
    def adjust(self, request, pk=None):
        balance = self.get_object()
        updated = adjust_balance(
            balance=balance,
            entitled=request.data.get("entitled"),
            actor=request.user,
            reason=request.data.get("reason", ""),
            request=request,
        )
        return Response(LeaveBalanceSerializer(updated).data)


class LeaveRequestViewSet(viewsets.ModelViewSet):
    serializer_class = LeaveRequestSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    filterset_fields = ["employee", "status", "leave_type"]
    search_fields = ["employee__first_name", "employee__last_name", "employee__employee_code", "reason"]
    ordering_fields = ["start_date", "created_at", "status"]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = LeaveRequest.objects.filter(employee__in=visible_employees(self.request.user)).select_related("employee", "leave_type", "reviewed_by")
        if self.request.query_params.get("from"):
            qs = qs.filter(end_date__gte=self.request.query_params["from"])
        if self.request.query_params.get("to"):
            qs = qs.filter(start_date__lte=self.request.query_params["to"])
        return qs

    def perform_create(self, serializer):
        employee = serializer.validated_data["employee"]
        if self.request.user.role == "employee":
            profile = getattr(self.request.user, "employee_profile", None)
            if profile is None or employee.id != profile.id:
                from apps.common.exceptions import BusinessError
                raise BusinessError("You can only request leave for yourself.", status_code=403)
        elif not visible_employees(self.request.user).filter(pk=employee.pk).exists():
            from apps.common.exceptions import BusinessError
            raise BusinessError("That employee is outside your access.", status_code=403)
        leave = submit_leave(
            employee=employee,
            leave_type=serializer.validated_data["leave_type"],
            start=serializer.validated_data["start_date"],
            end=serializer.validated_data["end_date"],
            day_part=serializer.validated_data.get("day_part") or "full",
            reason=serializer.validated_data.get("reason", ""),
            document=serializer.validated_data.get("document"),
            actor=self.request.user,
            request=self.request,
        )
        serializer.instance = leave

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        leave, warnings = decide_leave(leave=self.get_object(), actor=request.user, approve=True, note=request.data.get("note", ""), request=request)
        data = LeaveRequestSerializer(leave, context={"request": request}).data
        data["warnings"] = warnings
        return Response(data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        leave, _warnings = decide_leave(leave=self.get_object(), actor=request.user, approve=False, note=request.data.get("note", ""), request=request)
        return Response(LeaveRequestSerializer(leave, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        leave = cancel_leave(leave=self.get_object(), actor=request.user, request=request)
        return Response(LeaveRequestSerializer(leave, context={"request": request}).data)


class LeaveCalendarView(viewsets.ViewSet):
    def list(self, request):
        from datetime import datetime

        from apps.attendance.services import office_now
        from apps.common.dates import month_bounds
        from apps.organization.models import Holiday, OfficeSettings

        today = office_now().date()
        try:
            year = int(request.query_params.get("year", today.year))
            month = int(request.query_params.get("month", today.month))
        except ValueError:
            year, month = today.year, today.month
        start, end = month_bounds(year, month)
        requests = LeaveRequest.objects.filter(
            employee__in=visible_employees(request.user),
            status__in=[LeaveRequest.Status.PENDING, LeaveRequest.Status.APPROVED],
            start_date__lte=end,
            end_date__gte=start,
        ).select_related("employee", "leave_type")
        if request.query_params.get("department"):
            requests = requests.filter(employee__department_id=request.query_params["department"])
        holidays = Holiday.objects.filter(is_active=True, date__range=(start, end))
        return Response(
            {
                "year": year,
                "month": month,
                "requests": LeaveRequestSerializer(requests, many=True, context={"request": request}).data,
                "holidays": [{"id": item.id, "name": item.name, "date": item.date.isoformat(), "location": item.location_id} for item in holidays],
                "timezone": OfficeSettings.load().timezone,
            }
        )
