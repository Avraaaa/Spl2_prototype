"""Small PostgreSQL outbox worker with reclaimable leases."""

from datetime import timedelta
from hashlib import sha256

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import OutboxMessage


def process_due(*, limit: int = 100) -> int:
    if not getattr(settings, "NOTIFICATION_EMAIL_ENABLED", True):
        return 0
    processed = 0
    max_attempts = max(1, int(getattr(settings, "OUTBOX_MAX_ATTEMPTS", 5)))
    lease_seconds = max(1, int(getattr(settings, "OUTBOX_LEASE_SECONDS", 60)))
    for _ in range(limit):
        now = timezone.now()
        with transaction.atomic():
            message = (
                OutboxMessage.objects.select_for_update(skip_locked=True)
                .filter(
                    channel=OutboxMessage.Channel.EMAIL,
                    status__in=[OutboxMessage.Status.PENDING, OutboxMessage.Status.FAILED],
                    next_attempt_at__lte=now,
                )
                .filter(Q(locked_until__isnull=True) | Q(locked_until__lte=now))
                .first()
            )
            if message is None:
                break
            lease = now + timedelta(seconds=lease_seconds)
            message.locked_until = lease
            message.save(update_fields=["locked_until"])
        try:
            fingerprint = sha256(message.idempotency_key.encode()).hexdigest()
            email = EmailMessage(
                subject=message.payload["subject"],
                body=message.payload["body"],
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "notifications@example.test"),
                to=[message.payload["to"]],
                headers={"Message-ID": f"<{fingerprint}@datasoft.local>"},
            )
            sent = email.send(fail_silently=False)
            if sent != 1:
                raise RuntimeError("No email accepted")
        except Exception as exc:
            # Error text from a provider may contain credentials or message data.
            with transaction.atomic():
                current = OutboxMessage.objects.select_for_update().get(pk=message.pk)
                if current.locked_until == lease and current.status != OutboxMessage.Status.SENT:
                    current.attempts += 1
                    current.status = (
                        OutboxMessage.Status.DEAD
                        if current.attempts >= max_attempts
                        else OutboxMessage.Status.FAILED
                    )
                    seconds = min(3600, 30 * 2 ** min(current.attempts - 1, 10))
                    current.next_attempt_at = timezone.now() + timedelta(seconds=seconds)
                    current.locked_until = None
                    current.last_error = type(exc).__name__[:200]
                    current.save(
                        update_fields=[
                            "attempts",
                            "status",
                            "next_attempt_at",
                            "locked_until",
                            "last_error",
                        ]
                    )
        else:
            with transaction.atomic():
                current = OutboxMessage.objects.select_for_update().get(pk=message.pk)
                if current.locked_until == lease and current.status != OutboxMessage.Status.SENT:
                    current.attempts += 1
                    current.status = OutboxMessage.Status.SENT
                    current.locked_until = None
                    current.last_error = ""
                    current.save(update_fields=["attempts", "status", "locked_until", "last_error"])
        processed += 1
    return processed
