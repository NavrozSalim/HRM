from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.payroll.views import AdvanceViewSet, BonusViewSet, DeductionViewSet, PayrollPeriodViewSet, PayrollRecordViewSet

router = DefaultRouter()
router.register("payroll/periods", PayrollPeriodViewSet, basename="payroll-period")
router.register("payroll/records", PayrollRecordViewSet, basename="payroll-record")
router.register("payroll/advances", AdvanceViewSet, basename="salary-advance")
router.register("payroll/bonuses", BonusViewSet, basename="bonus")
router.register("payroll/deductions", DeductionViewSet, basename="deduction")

urlpatterns = [path("", include(router.urls))]
