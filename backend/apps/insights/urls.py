from django.urls import path

from apps.insights.views import AuditLogView, CompanyReportView, DashboardView, EmployeeReportView, ExportView, HealthView, SearchView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("reports/employee-monthly/", EmployeeReportView.as_view(), name="employee-report"),
    path("reports/company-monthly/", CompanyReportView.as_view(), name="company-report"),
    path("exports/<slug:kind>/", ExportView.as_view(), name="export"),
    path("search/", SearchView.as_view(), name="search"),
    path("audit-logs/", AuditLogView.as_view(), name="audit-logs"),
]
