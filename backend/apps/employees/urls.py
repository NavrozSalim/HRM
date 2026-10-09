from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.employees.views import AllowanceViewSet, EmployeeViewSet

router = DefaultRouter()
router.register("employees", EmployeeViewSet, basename="employee")
router.register("allowances", AllowanceViewSet, basename="allowance")

urlpatterns = [path("", include(router.urls))]
