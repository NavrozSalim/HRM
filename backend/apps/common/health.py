from django.db import connection
from django.urls import path
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        connection.ensure_connection()
        return Response({"status": "ok"})


urlpatterns = [
    path("", HealthView.as_view(), name="health"),
]
