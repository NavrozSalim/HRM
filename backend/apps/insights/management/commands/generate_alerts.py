from django.core.management.base import BaseCommand

from apps.notifications.services import generate_alerts


class Command(BaseCommand):
    help = "Create in-app alerts for late arrivals, missing attendance, leave, payroll, birthdays, and anniversaries."

    def handle(self, *args, **options):
        result = generate_alerts()
        self.stdout.write(str(result))
