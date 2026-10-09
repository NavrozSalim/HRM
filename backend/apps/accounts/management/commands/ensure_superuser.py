from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

User = get_user_model()


class Command(BaseCommand):
    help = "Create the super user from the environment when that account does not exist yet."

    def handle(self, *args, **options):
        username = (settings.SUPERUSER_USERNAME or "").strip()
        password = settings.SUPERUSER_PASSWORD or ""
        if not username or not password:
            raise CommandError("Set SUPERUSER_USERNAME and SUPERUSER_PASSWORD before starting the server.")
        if len(password) < 8:
            raise CommandError("SUPERUSER_PASSWORD must be at least 8 characters.")
        if User.objects.filter(username=username).exists():
            self.stdout.write(f"Super user '{username}' already exists. The password was left unchanged.")
            return
        User.objects.create_superuser(
            username,
            settings.SUPERUSER_EMAIL or "",
            password,
            first_name=settings.SUPERUSER_FIRST_NAME or "",
            last_name=settings.SUPERUSER_LAST_NAME or "",
            role=User.Role.SUPER_ADMIN,
        )
        self.stdout.write(self.style.SUCCESS(f"Super user '{username}' was created."))
