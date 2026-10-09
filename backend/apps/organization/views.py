from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.audit import audit
from apps.common.permissions import OrgWriteOrAuthenticatedRead, SettingsAccess
from apps.organization.models import Department, Holiday, JobTitle, OfficeLocation, OfficeSettings, Shift
from apps.organization.serializers import (
    DepartmentSerializer,
    HolidaySerializer,
    JobTitleSerializer,
    OfficeLocationSerializer,
    OfficeSettingsSerializer,
    ShiftSerializer,
)
from apps.payroll.services import mark_period_stale


class LocationViewSet(viewsets.ModelViewSet):
    queryset = OfficeLocation.objects.all()
    serializer_class = OfficeLocationSerializer
    permission_classes = [OrgWriteOrAuthenticatedRead]
    search_fields = ["name"]
    filterset_fields = ["is_active"]


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.select_related("manager", "location")
    serializer_class = DepartmentSerializer
    permission_classes = [OrgWriteOrAuthenticatedRead]
    search_fields = ["name", "code"]
    filterset_fields = ["is_active", "location"]


class JobTitleViewSet(viewsets.ModelViewSet):
    queryset = JobTitle.objects.select_related("department")
    serializer_class = JobTitleSerializer
    permission_classes = [OrgWriteOrAuthenticatedRead]
    search_fields = ["name"]
    filterset_fields = ["department", "is_active"]


class ShiftViewSet(viewsets.ModelViewSet):
    queryset = Shift.objects.all()
    serializer_class = ShiftSerializer
    permission_classes = [OrgWriteOrAuthenticatedRead]
    search_fields = ["name"]
    filterset_fields = ["is_active"]


class HolidayViewSet(viewsets.ModelViewSet):
    queryset = Holiday.objects.select_related("location")
    serializer_class = HolidaySerializer
    permission_classes = [OrgWriteOrAuthenticatedRead]
    search_fields = ["name"]
    filterset_fields = ["location", "is_active"]
    ordering_fields = ["date", "name"]


class OfficeSettingsView(APIView):
    permission_classes = [SettingsAccess]

    def get(self, request):
        return Response(OfficeSettingsSerializer(OfficeSettings.load()).data)

    def patch(self, request):
        office = OfficeSettings.load()
        serializer = OfficeSettingsSerializer(office, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        from datetime import date

        today = date.today()
        mark_period_stale(today.year, today.month)
        audit(actor=request.user, action="settings.update", instance=office, summary="Updated office attendance and payroll policy.", request=request)
        return Response(serializer.data)
