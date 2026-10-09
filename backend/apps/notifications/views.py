from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsHROrSuper
from apps.notifications.models import Notification
from apps.notifications.services import generate_alerts


class NotificationListView(APIView):
    def get(self, request):
        qs = Notification.objects.filter(recipient=request.user)
        if request.query_params.get("unread") == "1":
            qs = qs.filter(is_read=False)
        return Response(
            {
                "unread": Notification.objects.filter(recipient=request.user, is_read=False).count(),
                "results": [
                    {
                        "id": item.id,
                        "category": item.category,
                        "title": item.title,
                        "body": item.body,
                        "link": item.link,
                        "is_read": item.is_read,
                        "created_at": item.created_at.isoformat(),
                    }
                    for item in qs[:100]
                ],
            }
        )


class NotificationReadView(APIView):
    def post(self, request):
        qs = Notification.objects.filter(recipient=request.user, is_read=False)
        if not request.data.get("all"):
            qs = qs.filter(id__in=request.data.get("ids") or [])
        updated = qs.update(is_read=True)
        return Response({"updated": updated})


class GenerateAlertsView(APIView):
    permission_classes = [IsHROrSuper]

    def post(self, request):
        return Response(generate_alerts())
