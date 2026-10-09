from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.leaves.views import LeaveBalanceViewSet, LeaveCalendarView, LeaveRequestViewSet, LeaveTypeViewSet

router = DefaultRouter()
router.register("leave-types", LeaveTypeViewSet, basename="leave-type")
router.register("leave-balances", LeaveBalanceViewSet, basename="leave-balance")
router.register("leave-requests", LeaveRequestViewSet, basename="leave-request")
router.register("leave-calendar", LeaveCalendarView, basename="leave-calendar")

urlpatterns = [path("", include(router.urls))]
