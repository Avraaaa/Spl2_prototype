"""Create tenant-bound alerts and durable deliveries in the caller's transaction."""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from domains.accounts.roles import BANK_ROLES, DATASOFT_ROLES, Role
from domains.issues.models import Issue, IssueEvent, IssueStatus

from .models import Notification, OutboxMessage


def _bank_users(issue: Issue, roles: frozenset[str]):
    return User.objects.filter(
        is_active=True,
        account__organization=issue.organization,
        account__organization__is_active=True,
        memberships__organization=issue.organization,
        memberships__role__in=roles,
    ).distinct()


def _staff_users():
    return User.objects.filter(
        is_active=True,
        account__organization__kind="DATASOFT",
        account__organization__is_active=True,
        memberships__organization__kind="DATASOFT",
        memberships__organization__is_active=True,
        memberships__organization=F("account__organization"),
        memberships__role__in=DATASOFT_ROLES,
    ).distinct()


def _recipients(issue: Issue, kind: str):
    if kind == "SUBMITTED":
        return _staff_users()
    if kind in {"ACCEPTED", "REJECTED", "TENTATIVE_DATE_REVISED", "CLOSED"}:
        return _bank_users(issue, BANK_ROLES)
    if kind == "DELIVERED":
        return _bank_users(issue, frozenset({Role.ISSUE_VERIFIER}))
    if kind in {"VERIFIED", "VERIFICATION_FAILED"}:
        return _staff_users()
    if kind == "REOPENED":
        return _bank_users(issue, BANK_ROLES) | _staff_users()
    return User.objects.none()


@transaction.atomic
def notify(*, issue: Issue, recipient: User, kind: str, title: str, body: str, key: str) -> bool:
    """Idempotently publish one in-app alert and optional email delivery.

    Call inside the business transaction. The caller supplies a server-selected recipient.
    """
    if not (
        _bank_users(issue, BANK_ROLES).filter(pk=recipient.pk).exists()
        or _staff_users().filter(pk=recipient.pk).exists()
    ):
        raise ValueError("Notification recipient is outside the issue audience")
    now = timezone.now()
    _, created = OutboxMessage.objects.get_or_create(
        idempotency_key=f"{key}:in_app:{recipient.pk}",
        defaults={
            "channel": OutboxMessage.Channel.IN_APP,
            "recipient": recipient,
            "payload": {"kind": kind, "issue_id": issue.pk},
            "status": OutboxMessage.Status.SENT,
            "next_attempt_at": now,
        },
    )
    if created:
        Notification.objects.create(
            recipient=recipient,
            organization=issue.organization,
            issue=issue,
            kind=kind,
            title=title[:200],
            body=body,
        )
    if recipient.email:
        OutboxMessage.objects.get_or_create(
            idempotency_key=f"{key}:email:{recipient.pk}",
            defaults={
                "channel": OutboxMessage.Channel.EMAIL,
                "recipient": recipient,
                "payload": {"subject": title[:200], "body": body, "to": recipient.email},
                "next_attempt_at": now,
            },
        )
    return created


def notify_issue_event(event: IssueEvent) -> None:
    issue = event.issue
    title = f"{issue.reference}: {event.kind.replace('_', ' ').title()}"
    body = (
        f"Service request {issue.reference} has a new "
        f"{event.kind.replace('_', ' ').lower()} update."
    )
    for recipient in _recipients(issue, event.kind):
        notify(
            issue=issue,
            recipient=recipient,
            kind=event.kind,
            title=title,
            body=body,
            key=f"issue-event:{event.pk}",
        )


def send_verification_reminders() -> int:
    """Queue reminders once per calendar day after the waiting threshold."""
    days = max(1, int(getattr(settings, "VERIFICATION_REMINDER_DAYS", 3)))
    now = timezone.now()
    cutoff = now - timedelta(days=days)
    created = 0
    rows = Issue.objects.filter(
        status=IssueStatus.AWAITING_VERIFICATION,
        last_status_at__lte=cutoff,
    ).select_related("organization", "assignee")
    for issue in rows.iterator():
        key = f"verification-reminder:{issue.pk}:{issue.version}:{now.date().isoformat()}"
        recipients = list(_bank_users(issue, frozenset({Role.ISSUE_VERIFIER})))
        if issue.assignee_id and issue.assignee and issue.assignee.is_active:
            if _staff_users().filter(pk=issue.assignee_id).exists():
                recipients.append(issue.assignee)
        with transaction.atomic():
            for recipient in recipients:
                created += notify(
                    issue=issue,
                    recipient=recipient,
                    kind="VERIFICATION_REMINDER",
                    title=f"{issue.reference}: Verification reminder",
                    body=f"Service request {issue.reference} is awaiting client verification.",
                    key=key,
                )
    return created
