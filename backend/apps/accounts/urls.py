from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.accounts.views import ChangePasswordView, CompanyView, LoginView, LogoutView, MeView, RefreshView, UserViewSet

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", RefreshView.as_view(), name="refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("company/", CompanyView.as_view(), name="company"),
    path("", include(router.urls)),
]
