from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APITestCase

User = get_user_model()


class HealthTests(APITestCase):
    def test_health_is_public_and_checks_the_database(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")


class EnsureSuperuserTests(TestCase):
    def test_existing_superuser_password_is_left_alone(self):
        user = User.objects.create_user(settings.SUPERUSER_USERNAME, password="original-password", role=User.Role.SUPER_ADMIN)
        call_command("ensure_superuser")
        user.refresh_from_db()
        self.assertTrue(user.check_password("original-password"))

    def test_missing_superuser_is_created_once(self):
        call_command("ensure_superuser")
        user = User.objects.get(username=settings.SUPERUSER_USERNAME)
        self.assertEqual(user.role, User.Role.SUPER_ADMIN)
        self.assertTrue(user.is_superuser)
        call_command("ensure_superuser")
        self.assertEqual(User.objects.filter(username=settings.SUPERUSER_USERNAME).count(), 1)
