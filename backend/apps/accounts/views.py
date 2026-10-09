from django.contrib.auth import get_user_model
from rest_framework import mixins, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.serializers import ChangePasswordSerializer, LoginSerializer, UserSerializer
from apps.common.audit import audit
from apps.common.exceptions import BusinessError
from apps.common.permissions import IsSuperAdmin
from apps.organization.models import OfficeSettings

User = get_user_model()


class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer


class RefreshView(TokenRefreshView):
    permission_classes = [AllowAny]


class LogoutView(APIView):
    def post(self, request):
        token = request.data.get("refresh")
        if not token:
            raise BusinessError("A refresh token is required.")
        try:
            RefreshToken(token).blacklist()
        except Exception as exc:
            raise BusinessError("The refresh token is invalid or already expired.") from exc
        return Response({"detail": "Signed out."})


class MeView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class ChangePasswordView(APIView):
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        if not request.user.check_password(serializer.validated_data["old_password"]):
            raise BusinessError("The current password is incorrect.")
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        audit(actor=request.user, action="auth.password", instance=request.user, summary=f"{request.user.display_name} changed their password.", request=request)
        return Response({"detail": "Password updated."})


class CompanyView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        office = OfficeSettings.load()
        return Response({"company_name": office.company_name, "currency": office.currency})


class UserViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = UserSerializer
    permission_classes = [IsSuperAdmin]
    search_fields = ["username", "first_name", "last_name", "email"]
    ordering_fields = ["username", "role", "is_active"]
    queryset = User.objects.all().order_by("username")

    def perform_create(self, serializer):
        user = serializer.save()
        audit(actor=self.request.user, action="user.create", instance=user, summary=f"Created the {user.role} account {user.username}.", request=self.request)

    def perform_update(self, serializer):
        instance = serializer.instance
        new_role = serializer.validated_data.get("role", instance.role)
        new_active = serializer.validated_data.get("is_active", instance.is_active)
        if instance.role == User.Role.SUPER_ADMIN and (new_role != User.Role.SUPER_ADMIN or not new_active):
            remaining = User.objects.filter(role=User.Role.SUPER_ADMIN, is_active=True).exclude(pk=instance.pk).count()
            if remaining == 0:
                raise BusinessError("Keep at least one active super admin.")
        user = serializer.save()
        audit(actor=self.request.user, action="user.update", instance=user, summary=f"Updated the account {user.username}.", request=self.request)
