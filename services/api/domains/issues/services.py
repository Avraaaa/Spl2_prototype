"""Bank-owned draft writes and the officer's atomic submission action."""

import re
from functools import partial

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from domains.accounts.models import Membership
from domains.accounts.roles import Role
from domains.notifications.services import notify_issue_event
from domains.tenants.models import OrganizationKind
from domains.tenants.selectors import (
    authorized_rows,
    get_authorized_object_or_404,
    portal_organization,
)

from .models import Issue, IssueEvent, IssueStatus, RequestType

TEXT_FIELDS = frozenset(
    {
        "title",
        "description",
        "environment",
        "steps_to_reproduce",
        "expected_result",
        "actual_result",
    }
)

OTP_KEYWORDS = re.compile(
    r"(?<![\w\u0980-\u09ff])"
    r"(?:otp(?: +code)?|one[- ]time[- ](?:password|passcode|code)"
    r"|verification +code|security +code|passcode|pin|tpin|mpin"
    r"|ওটিপি|পিন|ভেরিফিকেশন +কোড)"
    r"(?![\w\u0980-\u09ff])",
    re.IGNORECASE,
)
OTP_DIGITS = re.compile(r"(?<![\w\u0980-\u09ff])[0-9\u09e6-\u09ef]{4,8}(?![\w\u0980-\u09ff])")
SENTENCE_TEXT = re.compile(r"[^.!?\u0964\r\n]+")


def is_officer(user: User) -> bool:
    organization = portal_organization(user)
    return bool(
        organization
        and organization.kind == OrganizationKind.BANK
        and Membership.objects.filter(
            user=user, organization=organization, role=Role.ISSUE_OFFICER
        ).exists()
    )


def _mask_otp_in_sentence(sentence: re.Match[str]) -> str:
    text = sentence.group()
    keywords = [match.span() for match in OTP_KEYWORDS.finditer(text)]
    if not keywords:
        return text

    def replace_digits(token: re.Match[str]) -> str:
        start, end = token.span()
        for keyword_start, keyword_end in keywords:
            gap = max(keyword_start - end, start - keyword_end)
            if gap <= 40:
                return "[OTP REDACTED]"
        return token.group()

    return OTP_DIGITS.sub(replace_digits, text)


def mask_sensitive(value: str) -> str:
    """Mask PANs and nearby OTP/PIN tokens before persistence; human review is still needed."""
    value = re.sub(r"(?<!\d)(?:\d[ .-]?){12,18}\d(?!\d)", "[CARD REDACTED]", value)
    return SENTENCE_TEXT.sub(_mask_otp_in_sentence, value)


def _clean(fields: dict) -> dict:
    cleaned = {
        key: mask_sensitive(value) if key in TEXT_FIELDS else value for key, value in fields.items()
    }
    if "title" in cleaned and len(cleaned["title"]) > 200:
        raise ValidationError({"title": "Masked title must be 200 characters or fewer."})
    return cleaned


def _validate_links(user: User, fields: dict, existing: Issue | None = None) -> None:
    product = fields.get("product", existing.product if existing else None)
    module = fields.get("module", existing.module if existing else None)
    if module and (product is None or module.product_id != product.pk):
        raise ValidationError({"module": "Module must belong to the product."})
    related = fields.get("related_request", existing.related_request if existing else None)
    if related:
        allowed = authorized_rows(user, Issue.objects.exclude(status=IssueStatus.DRAFT))
        if not allowed.filter(pk=related.pk).exists() or (existing and related.pk == existing.pk):
            raise ValidationError({"related_request": "Invalid related request."})


def create_draft(user, fields: dict) -> Issue:
    organization = portal_organization(user)
    if not is_officer(user) or organization is None:
        raise PermissionDenied("Issue Officer role required.")
    with transaction.atomic():
        _validate_links(user, fields)
        issue = Issue.objects.create(organization=organization, created_by=user, **_clean(fields))
        # BigAutoField uses the database sequence; this reference is immutable thereafter.
        issue.reference = f"SR-{issue.pk + 1023}"
        issue.save(update_fields=["reference", "updated_at"])
    return issue


def edit_draft(user, issue: Issue, fields: dict) -> Issue:
    from .workflow import VersionConflict

    with transaction.atomic():
        locked = get_authorized_object_or_404(user, Issue.objects.select_for_update(), issue.pk)
        if (
            not is_officer(user)
            or locked.created_by_id != user.pk
            or locked.status != IssueStatus.DRAFT
        ):
            raise PermissionDenied("Only the creator can edit this draft.")
        if "version" in fields and locked.version != fields["version"]:
            raise VersionConflict("This request was changed by someone else — reload.")
        _validate_links(user, fields, locked)
        changes = {key: value for key, value in fields.items() if key != "version"}
        for key, value in _clean(changes).items():
            setattr(locked, key, value)
        locked.version += 1
        locked.save()
    return locked


def delete_draft(user, issue: Issue) -> None:
    with transaction.atomic():
        locked = get_authorized_object_or_404(user, Issue.objects.select_for_update(), issue.pk)
        if (
            not is_officer(user)
            or locked.created_by_id != user.pk
            or locked.status != IssueStatus.DRAFT
        ):
            raise PermissionDenied("Only the creator can delete this draft.")
        for attachment in locked.attachments.all():
            stored_name = attachment.file.name
            if stored_name:
                transaction.on_commit(
                    partial(attachment.file.storage.delete, stored_name), robust=True
                )
        locked.attachments.all().delete()
        locked.comments.all().delete()
        locked.delete()


def submit(user, issue: Issue) -> Issue:
    with transaction.atomic():
        locked = get_authorized_object_or_404(user, Issue.objects.select_for_update(), issue.pk)
        if not is_officer(user) or locked.created_by_id != user.pk:
            raise PermissionDenied("Only the creator can submit this draft.")
        if locked.status != IssueStatus.DRAFT:
            raise ValidationError({"status": "Only a draft can be submitted."})
        required = ("title", "description", "request_type", "product", "priority")
        missing = [key for key in required if not getattr(locked, key)]
        if locked.request_type == RequestType.BUG:
            evidence = ("environment", "steps_to_reproduce", "expected_result", "actual_result")
            missing.extend(key for key in evidence if not getattr(locked, key).strip())
        if missing:
            raise ValidationError({key: "Required before submission." for key in missing})
        locked.status = IssueStatus.SUBMITTED
        locked.submitted_by = user
        locked.submitted_at = timezone.now()
        locked.last_status_at = locked.submitted_at
        locked.version += 1
        locked.save(
            update_fields=[
                "status",
                "submitted_by",
                "submitted_at",
                "last_status_at",
                "version",
                "updated_at",
            ]
        )
        event = IssueEvent.objects.create(
            issue=locked,
            actor=user,
            kind="SUBMITTED",
            from_status=IssueStatus.DRAFT,
            to_status=IssueStatus.SUBMITTED,
        )
        notify_issue_event(event)
    return locked
