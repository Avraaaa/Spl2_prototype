from django.core.management.base import BaseCommand

from domains.notifications.worker import process_due


class Command(BaseCommand):
    help = "Process due email outbox rows"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        count = process_due(limit=max(0, options["limit"]))
        self.stdout.write(f"Processed {count} outbox rows")
