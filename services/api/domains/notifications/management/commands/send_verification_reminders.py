from django.core.management.base import BaseCommand

from domains.notifications.services import send_verification_reminders


class Command(BaseCommand):
    help = "Queue due client verification reminders"

    def handle(self, *args, **options):
        count = send_verification_reminders()
        self.stdout.write(f"Queued {count} reminders")
