"""Regression tests for notification periods and outbox claim ownership."""

from datetime import timedelta

import pytest
from django.utils import timezone

from domains.accounts.roles import Role
from domains.issues.models import Issue, IssueStatus
from domains.issues.workflow import deliver
from domains.notifications.models import Notification, OutboxMessage
from domains.notifications.services import send_verification_reminders
from domains.notifications.worker import _send_claimed


@pytest.mark.django_db
def test_reminder_repeats_only_after_another_configured_period(
    bank_a, officer_a, support, make_user, settings
):
    verifier = make_user("period_verifier", bank_a, Role.ISSUE_VERIFIER)
    issue = Issue.objects.create(
        organization=bank_a,
        created_by=officer_a,
        submitted_by=officer_a,
        title="Reminder period regression",
        status=IssueStatus.IN_PROGRESS,
        assignee=support,
        reference="SR-9910",
    )
    deliver(support, issue.pk, issue.version, delivery_note="done", deployment_details="v1")
    settings.VERIFICATION_REMINDER_DAYS = 3

    Issue.objects.filter(pk=issue.pk).update(last_status_at=timezone.now() - timedelta(days=4))
    assert send_verification_reminders() > 0
    assert send_verification_reminders() == 0

    Issue.objects.filter(pk=issue.pk).update(last_status_at=timezone.now() - timedelta(days=7))
    assert send_verification_reminders() > 0
    assert (
        Notification.objects.filter(recipient=verifier, kind="VERIFICATION_REMINDER").count() == 2
    )


@pytest.mark.django_db
def test_stale_worker_cannot_send_a_claim_owned_by_another_worker(settings, support):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    now = timezone.now()
    message = OutboxMessage.objects.create(
        channel=OutboxMessage.Channel.EMAIL,
        recipient=support,
        payload={"subject": "Synthetic", "body": "Body", "to": "support@example.test"},
        idempotency_key="claim-ownership-regression",
        next_attempt_at=now,
        locked_until=now + timedelta(seconds=60),
    )

    stale_lease = now + timedelta(seconds=30)
    assert _send_claimed(message.pk, stale_lease, max_attempts=3) is False
    message.refresh_from_db()
    assert message.status == OutboxMessage.Status.PENDING
    assert message.attempts == 0
