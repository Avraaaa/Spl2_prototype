"""Small PostgreSQL outbox worker with reclaimable leases."""

from datetime import datetime, timedelta
from hashlib import sha256

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.html import escape

from .models import OutboxMessage

REDACTED_EMAIL_CONTENT = "[REDACTED AFTER DELIVERY]"


def _send_claimed(message_id: int, lease: datetime, *, max_attempts: int) -> bool:
    """Send a claimed message while its database row remains locked.

    The persistent lease enables recovery after a crashed worker. The row lock
    prevents a second worker from reclaiming and sending the same message when
    a slow mail backend outlives that lease.
    """
    with transaction.atomic():
        current = OutboxMessage.objects.select_for_update().get(pk=message_id)
        if current.locked_until != lease or current.status == OutboxMessage.Status.SENT:
            return False

        try:
            fingerprint = sha256(current.idempotency_key.encode()).hexdigest()
            headers = {"Message-ID": f"<{fingerprint}@datasoft.local>"}
            if getattr(settings, "EMAIL_REPLY_TO", ""):
                headers["Reply-To"] = settings.EMAIL_REPLY_TO
            email = EmailMultiAlternatives(
                subject=current.payload["subject"],
                body=current.payload["body"],
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "notifications@example.test"),
                to=[current.payload["to"]],
                headers=headers,
            )
            html_body = current.payload.get("html") or (
                f"<p>{escape(current.payload['body']).replace(chr(10), '<br>')}</p>"
            )
            email.attach_alternative(html_body, "text/html")
            sent = email.send(fail_silently=False)
            if sent != 1:
                raise RuntimeError("No email accepted")
        except Exception as exc:
            # Provider errors may contain credentials or message data. Store
            # only the exception type, never its message.
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
            if current.status == OutboxMessage.Status.DEAD:
                current.payload = _scrub_email_payload(current.payload)
            current.save(
                update_fields=[
                    "attempts",
                    "status",
                    "next_attempt_at",
                    "locked_until",
                    "last_error",
                    "payload",
                ]
            )
        else:
            current.attempts += 1
            current.status = OutboxMessage.Status.SENT
            current.locked_until = None
            current.last_error = ""
            current.payload = _scrub_email_payload(current.payload)
            current.save(
                update_fields=["attempts", "status", "locked_until", "last_error", "payload"]
            )
        return True


def _scrub_email_payload(payload: dict) -> dict:
    scrubbed = dict(payload)
    if "body" in scrubbed:
        scrubbed["body"] = REDACTED_EMAIL_CONTENT
    if "html" in scrubbed:
        scrubbed["html"] = REDACTED_EMAIL_CONTENT
    return scrubbed


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
        if _send_claimed(message.pk, lease, max_attempts=max_attempts):
            processed += 1
    return processed
