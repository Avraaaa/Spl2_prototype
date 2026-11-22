"""Named, locked transitions for the client-visible issue lifecycle."""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from domains.accounts.models import Membership
from domains.accounts.roles import BANK_ROLES, DATASOFT_ROLES, Role
from domains.notifications.services import notify_issue_event
from domains.tenants.models import OrganizationKind
from domains.tenants.selectors import get_authorized_object_or_404, portal_organization

from .models import Issue, IssueEvent, IssueStatus, WorkflowSettings
from .services import mask_sensitive


class VersionConflict(Exception):
    """The client edited a version that is no longer current."""


def _role(user: User, allowed: frozenset[str]) -> bool:
    organization = portal_organization(user)
    if organization is None:
        return False
    valid_roles = BANK_ROLES if organization.kind == OrganizationKind.BANK else DATASOFT_ROLES
    return bool(
        Membership.objects.filter(
            user=user, organization=organization, role__in=allowed & valid_roles
        ).exists()
    )


def _locked(
    user: User, issue_id: int, version: int, states: frozenset[str], roles: frozenset[str]
) -> Issue:
    organization = portal_organization(user)
    rows = Issue.objects.select_for_update()
    if organization and organization.kind == OrganizationKind.DATASOFT:
        rows = rows.exclude(status=IssueStatus.DRAFT)
    issue = get_authorized_object_or_404(user, rows, issue_id, allow_datasoft=True)
    if not _role(user, roles):
        raise PermissionDenied("Role is not allowed for this action.")
    if issue.version != version:
        raise VersionConflict("This request was changed by someone else — reload.")
    if issue.status not in states:
        raise ValidationError({"status": "Action is not allowed in the current status."})
    return issue


def _record(
    issue: Issue,
    actor: User,
    kind: str,
    prior: str,
    *,
    reason: str = "",
    comment: str = "",
    details: dict | None = None,
) -> Issue:
    now = timezone.now()
    if issue.status != prior:
        issue.last_status_at = now
    issue.version += 1
    issue.save()
    event = IssueEvent.objects.create(
        issue=issue,
        actor=actor,
        kind=kind,
        from_status=prior,
        to_status=issue.status,
        reason=mask_sensitive(reason),
        details={
            **(details or {}),
            **({"comment": mask_sensitive(comment.strip())} if comment.strip() else {}),
        },
    )
    notify_issue_event(event)
    return issue


def _required(value: str, field: str) -> str:
    cleaned = mask_sensitive(value.strip())
    if not cleaned:
        raise ValidationError({field: "This field is required."})
    return cleaned


def _date_input(delivery_date: date | None, later: bool) -> None:
    if (delivery_date is None) == (not later):
        raise ValidationError(
            {"tentative_delivery_date": "Choose a date or mark it to be provided later."}
        )


@transaction.atomic
def accept(
    user: User,
    issue_id: int,
    version: int,
    *,
    tentative_delivery_date: date | None = None,
    tentative_delivery_later: bool = False,
    comment: str = "",
) -> Issue:
    issue = _locked(user, issue_id, version, frozenset({IssueStatus.SUBMITTED}), DATASOFT_ROLES)
    _date_input(tentative_delivery_date, tentative_delivery_later)
    prior = issue.status
    issue.status = IssueStatus.ACCEPTED
    issue.tentative_delivery_date = tentative_delivery_date
    issue.tentative_delivery_later = tentative_delivery_later
    return _record(
        issue,
        user,
        "ACCEPTED",
        prior,
        details={
            "tentative_delivery_date": str(tentative_delivery_date)
            if tentative_delivery_date
            else None,
            "tentative_delivery_later": tentative_delivery_later,
        },
        comment=comment,
    )


@transaction.atomic
def reject(user: User, issue_id: int, version: int, *, reason: str, comment: str = "") -> Issue:
    issue = _locked(user, issue_id, version, frozenset({IssueStatus.SUBMITTED}), DATASOFT_ROLES)
    reason = _required(reason, "reason")
    prior = issue.status
    issue.status = IssueStatus.REJECTED
    return _record(issue, user, "REJECTED", prior, reason=reason, comment=comment)


@transaction.atomic
def revise_date(
    user: User,
    issue_id: int,
    version: int,
    *,
    tentative_delivery_date: date | None = None,
    tentative_delivery_later: bool = False,
    comment: str = "",
) -> Issue:
    issue = _locked(
        user,
        issue_id,
        version,
        frozenset({IssueStatus.ACCEPTED, IssueStatus.PENDING, IssueStatus.IN_PROGRESS}),
        DATASOFT_ROLES,
    )
    _date_input(tentative_delivery_date, tentative_delivery_later)
    old = issue.tentative_delivery_date
    old_later = issue.tentative_delivery_later
    if old == tentative_delivery_date and old_later == tentative_delivery_later:
        raise ValidationError({"tentative_delivery_date": "The tentative date has not changed."})
    issue.tentative_delivery_date = tentative_delivery_date
    issue.tentative_delivery_later = tentative_delivery_later
    return _record(
        issue,
        user,
        "TENTATIVE_DATE_REVISED",
        issue.status,
        details={
            "from_date": str(old) if old else None,
            "from_later": old_later,
            "to_date": str(tentative_delivery_date) if tentative_delivery_date else None,
            "to_later": tentative_delivery_later,
        },
        comment=comment,
    )


@transaction.atomic
def assign(user: User, issue_id: int, version: int, *, assignee: User, comment: str = "") -> Issue:
    issue = _locked(
        user,
        issue_id,
        version,
        frozenset({IssueStatus.ACCEPTED, IssueStatus.PENDING, IssueStatus.IN_PROGRESS}),
        DATASOFT_ROLES,
    )
    if not assignee.is_active or not _role(assignee, DATASOFT_ROLES):
        raise ValidationError({"assignee": "Choose an active DataSoft user."})
    prior = issue.status
    old_assignee = issue.assignee_id
    issue.assignee = assignee
    if issue.status == IssueStatus.ACCEPTED:
        issue.status = IssueStatus.PENDING
    return _record(
        issue,
        user,
        "ASSIGNED" if old_assignee is None else "REASSIGNED",
        prior,
        details={"from_assignee": old_assignee, "to_assignee": assignee.pk},
        comment=comment,
    )


@transaction.atomic
def start(user: User, issue_id: int, version: int, *, comment: str = "") -> Issue:
    issue = _locked(user, issue_id, version, frozenset({IssueStatus.PENDING}), DATASOFT_ROLES)
    prior = issue.status
    issue.status = IssueStatus.IN_PROGRESS
    return _record(issue, user, "STARTED", prior, comment=comment)


@transaction.atomic
def deliver(
    user: User,
    issue_id: int,
    version: int,
    *,
    delivery_note: str,
    deployment_details: str,
    comment: str = "",
) -> Issue:
    issue = _locked(user, issue_id, version, frozenset({IssueStatus.IN_PROGRESS}), DATASOFT_ROLES)
    note = _required(delivery_note, "delivery_note")
    deployment = _required(deployment_details, "deployment_details")
    prior = issue.status
    issue.status = IssueStatus.AWAITING_VERIFICATION
    issue.delivery_note = note
    issue.deployment_details = deployment
    delivered_at = timezone.now()
    issue.actual_delivery_at = delivered_at
    return _record(
        issue,
        user,
        "DELIVERED",
        prior,
        details={
            "delivery_note": note,
            "deployment_details": deployment,
            "actual_delivery_at": delivered_at.isoformat(),
        },
        comment=comment,
    )


@transaction.atomic
def verify(user: User, issue_id: int, version: int, *, comment: str = "") -> Issue:
    issue = _locked(
        user,
        issue_id,
        version,
        frozenset({IssueStatus.AWAITING_VERIFICATION}),
        frozenset({Role.ISSUE_VERIFIER}),
    )
    prior = issue.status
    issue.status = IssueStatus.VERIFIED
    return _record(issue, user, "VERIFIED", prior, comment=comment)


@transaction.atomic
def fail_verification(
    user: User, issue_id: int, version: int, *, reason: str, comment: str = ""
) -> Issue:
    issue = _locked(
        user,
        issue_id,
        version,
        frozenset({IssueStatus.AWAITING_VERIFICATION}),
        frozenset({Role.ISSUE_VERIFIER}),
    )
    reason = _required(reason, "reason")
    prior = issue.status
    issue.status = IssueStatus.IN_PROGRESS
    issue.actual_delivery_at = None
    return _record(issue, user, "VERIFICATION_FAILED", prior, reason=reason, comment=comment)


@transaction.atomic
def close(user: User, issue_id: int, version: int, *, comment: str = "") -> Issue:
    issue = _locked(user, issue_id, version, frozenset({IssueStatus.VERIFIED}), DATASOFT_ROLES)
    prior = issue.status
    issue.status = IssueStatus.CLOSED
    issue.closed_at = timezone.now()
    return _record(issue, user, "CLOSED", prior, comment=comment)


@transaction.atomic
def reopen(user: User, issue_id: int, version: int, *, reason: str, comment: str = "") -> Issue:
    issue = _locked(
        user, issue_id, version, frozenset({IssueStatus.CLOSED}), BANK_ROLES | DATASOFT_ROLES
    )
    reason = _required(reason, "reason")
    setting, _ = WorkflowSettings.objects.get_or_create(pk=1)
    if issue.closed_at is None or timezone.now() > issue.closed_at + timedelta(
        days=setting.reopen_days
    ):
        raise ValidationError(
            {
                "status": (
                    "Reopen window expired. Create a new Recurring request linked to this request."
                )
            }
        )
    prior = issue.status
    issue.status = IssueStatus.IN_PROGRESS
    issue.closed_at = None
    issue.actual_delivery_at = None
    return _record(issue, user, "REOPENED", prior, reason=reason, comment=comment)
