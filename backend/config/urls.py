from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/", include("apps.organization.urls")),
    path("api/", include("apps.employees.urls")),
    path("api/", include("apps.attendance.urls")),
    path("api/", include("apps.leaves.urls")),
    path("api/", include("apps.payroll.urls")),
    path("api/", include("apps.notifications.urls")),
    path("api/", include("apps.insights.urls")),
    path("api/health/", include("apps.common.health")),
]

if settings.SHOW_API_DOCS:
    urlpatterns += [
        path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
        path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger"),
    ]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = "Wesolucions HRM"
admin.site.site_title = "Wesolucions HRM"
admin.site.index_title = "Office administration"
