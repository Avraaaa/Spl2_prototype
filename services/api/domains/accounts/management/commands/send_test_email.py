from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Send a test message through the configured account email backend."

    def add_arguments(self, parser):
        parser.add_argument("--to", required=True)

    def handle(self, *args, **options):
        from django.conf import settings

        if not settings.DEFAULT_FROM_EMAIL:
            raise CommandError("Set EMAIL_FROM before sending a test email.")
        sent = send_mail(
            "DataSoft portal email test",
            "This confirms that the configured email backend can deliver messages.",
            settings.DEFAULT_FROM_EMAIL,
            [options["to"]],
            fail_silently=False,
        )
        if sent != 1:
            raise CommandError("The email backend did not accept the test message.")
        self.stdout.write("Test email accepted by the configured backend.")
