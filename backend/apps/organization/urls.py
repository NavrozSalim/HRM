from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.organization.views import DepartmentViewSet, HolidayViewSet, JobTitleViewSet, LocationViewSet, OfficeSettingsView, ShiftViewSet

router = DefaultRouter()
router.register("locations", LocationViewSet, basename="location")
router.register("departments", DepartmentViewSet, basename="department")
router.register("job-titles", JobTitleViewSet, basename="job-title")
router.register("shifts", ShiftViewSet, basename="shift")
router.register("holidays", HolidayViewSet, basename="holiday")

urlpatterns = [
    path("office-settings/", OfficeSettingsView.as_view(), name="office-settings"),
    path("", include(router.urls)),
]
