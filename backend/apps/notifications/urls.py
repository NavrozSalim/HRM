from django.urls import path

from apps.notifications.views import GenerateAlertsView, NotificationListView, NotificationReadView

urlpatterns = [
    path("notifications/", NotificationListView.as_view(), name="notifications"),
    path("notifications/read/", NotificationReadView.as_view(), name="notifications-read"),
    path("notifications/generate/", GenerateAlertsView.as_view(), name="notifications-generate"),
]
