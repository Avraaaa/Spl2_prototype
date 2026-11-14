"""Synthetic notification, outbox, and reminder behavior."""

from datetime import timedelta

import pytest
from django.core import mail
from django.core.mail.backends.base import BaseEmailBackend
from django.db import transaction
from django.http import Http404
from django.utils import timezone

from domains.accounts.roles import Role
from domains.issues.models import Issue, IssueEvent, IssueStatus
from domains.issues.workflow import deliver
from domains.notifications.models import Notification, OutboxMessage
from domains.notifications.services import send_verification_reminders
from domains.notifications.worker import process_due

from .conftest import client_for


@pytest.fixture
def waiting_issue(bank_a, officer_a, support, make_user):
    verifier = make_user("verifier_a", bank_a, Role.ISSUE_VERIFIER)
    issue = Issue.objects.create(
        organization=bank_a,
        created_by=officer_a,
        submitted_by=officer_a,
        title="Synthetic request",
        status=IssueStatus.IN_PROGRESS,
        assignee=support,
        reference="SR-9001",
    )
    return issue, verifier


@pytest.mark.django_db
def test_delivery_notifies_only_issue_bank_and_rolls_back(waiting_issue, officer_b):
    issue, verifier = waiting_issue
    with pytest.raises(Http404), transaction.atomic():
        deliver(officer_b, issue.pk, issue.version, delivery_note="done", deployment_details="v1")
        # Cross-bank actor is forbidden before any writes.
    assert not Notification.objects.exists()
    assert not OutboxMessage.objects.exists()

    with pytest.raises(RuntimeError), transaction.atomic():
        deliver(
            issue.assignee,
            issue.pk,
            issue.version,
            delivery_note="done",
            deployment_details="v1",
        )
        assert Notification.objects.filter(recipient=verifier).exists()
        raise RuntimeError("abort")
    assert not IssueEvent.objects.filter(issue=issue).exists()
    assert not Notification.objects.exists()
    assert not OutboxMessage.objects.exists()


@pytest.mark.django_db
def test_delivery_recipient_isolation(waiting_issue, officer_b, bank_b, make_user):
    issue, verifier = waiting_issue
    other_verifier = make_user("verifier_b", bank_b, Role.ISSUE_VERIFIER)
    deliver(issue.assignee, issue.pk, issue.version, delivery_note="done", deployment_details="v1")
    assert Notification.objects.filter(recipient=verifier, issue=issue).exists()
    assert not Notification.objects.filter(recipient__in=[officer_b, other_verifier]).exists()
    assert not OutboxMessage.objects.filter(recipient__in=[officer_b, other_verifier]).exists()


class FailingEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        raise RuntimeError("secret backend detail")


@pytest.mark.django_db
def test_failed_email_retries_then_dies_without_reverting_workflow(waiting_issue, settings):
    issue, _ = waiting_issue
    deliver(issue.assignee, issue.pk, issue.version, delivery_note="done", deployment_details="v1")
    settings.EMAIL_BACKEND = "tests.test_notifications.FailingEmailBackend"
    settings.OUTBOX_MAX_ATTEMPTS = 2
    assert process_due() > 0
    message = OutboxMessage.objects.filter(channel="email").first()
    assert message.status == "failed" and message.attempts == 1
    assert message.next_attempt_at > timezone.now()
    assert "secret" not in message.last_error
    OutboxMessage.objects.filter(pk=message.pk).update(next_attempt_at=timezone.now())
    process_due()
    message.refresh_from_db()
    issue.refresh_from_db()
    assert message.status == "dead" and message.attempts == 2
    assert issue.status == IssueStatus.AWAITING_VERIFICATION


@pytest.mark.django_db
def test_successful_email_is_sent_once_and_disabled_worker_keeps_queue(waiting_issue, settings):
    issue, _ = waiting_issue
    deliver(issue.assignee, issue.pk, issue.version, delivery_note="done", deployment_details="v1")
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.NOTIFICATION_EMAIL_ENABLED = False
    assert process_due() == 0
    assert OutboxMessage.objects.filter(channel="email", status="pending").exists()
    settings.NOTIFICATION_EMAIL_ENABLED = True
    assert process_due() == 1
    assert process_due() == 0
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_reminders_are_idempotent_and_do_not_change_status(waiting_issue, settings):
    issue, verifier = waiting_issue
    deliver(issue.assignee, issue.pk, issue.version, delivery_note="done", deployment_details="v1")
    Issue.objects.filter(pk=issue.pk).update(last_status_at=timezone.now() - timedelta(days=4))
    settings.VERIFICATION_REMINDER_DAYS = 3
    first = send_verification_reminders()
    second = send_verification_reminders()
    assert first > 0 and second == 0
    assert (
        Notification.objects.filter(recipient=verifier, kind="VERIFICATION_REMINDER").count() == 1
    )
    issue.refresh_from_db()
    assert issue.status == IssueStatus.AWAITING_VERIFICATION


@pytest.mark.django_db
def test_api_sees_only_own_notifications(waiting_issue, officer_b):
    issue, verifier = waiting_issue
    deliver(issue.assignee, issue.pk, issue.version, delivery_note="done", deployment_details="v1")
    own = client_for(verifier)
    other = client_for(officer_b)
    rows = own.get("/api/notifications/")
    assert rows.status_code == 200 and len(rows.data) == 1
    notification_id = rows.data[0]["id"]
    assert other.get("/api/notifications/").data == []
    assert other.post(f"/api/notifications/{notification_id}/read/").status_code == 404
    assert own.get("/api/notifications/unread-count/").data["count"] == 1
    assert own.post(f"/api/notifications/{notification_id}/read/").status_code == 200
    assert own.get("/api/notifications/unread-count/").data["count"] == 0
    assert own.post("/api/notifications/read-all/").status_code == 200
