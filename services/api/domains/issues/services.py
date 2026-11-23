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
        "acceptance_criteria",
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
OTP_DIGITS = re.compile(
    r"(?<![\w\u0980-\u09ff])(?<![A-Za-z]-)(?<![0-9\u09e6-\u09ef][./,])"
    r"[0-9\u09e6-\u09ef]{4,8}(?![\w\u0980-\u09ff])"
    r"(?![./,][0-9\u09e6-\u09ef])"
)
SENTENCE_TEXT = re.compile(r"[^.!?\u0964\r\n]+")
CARD_DIGITS = re.compile(r"(?<!\d)(?:\d[ .-]?){12,18}\d(?!\d)")
CARD_DIGIT_TRANSLATION = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹০১২৩৪৫৬৭৮৯",
    "012345678901234567890123456789",
)
ACCOUNT_NUMBER = re.compile(
    r"(?i)(?<![\w\u0980-\u09ff])(?:account|acount|a/c|acct|hisab|account\s+no(?:\.|\s+number)?|"
    r"হিসাব(?:\s+নম্বর)?)"
    r"(?:[^0-9\u09e6-\u09ef\r\n]{0,24})(?:[0-9\u09e6-\u09ef][ -]?){7,19}"
    r"[0-9\u09e6-\u09ef](?![0-9\u09e6-\u09ef])"
)
PHONE_NUMBER = re.compile(
    r"(?<![0-9\u09e6-\u09ef])(?:\+?[8৮][8৮][0০][1১]|[0০][1১])"
    r"[ -]?[0-9\u09e6-\u09ef]{3}"
    r"[ -]?[0-9\u09e6-\u09ef]{3}[ -]?[0-9\u09e6-\u09ef]{2,3}"
    r"(?![0-9\u09e6-\u09ef])"
)
EMAIL_ADDRESS = re.compile(
    r"(?i)(?<![\w.+-])[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?"
    r"(?:\.[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?)+"
)
NID_KEYWORDS = re.compile(
    r"(?i)(?:\bnid\b|\bnational\s+id\b|"
    r"\u099c\u09be\u09a4\u09c0(?:\u09af\u09bc|\u09df)\s*"
    r"\u09aa\u09b0\u09bf\u099a(?:\u09af\u09bc|\u09df)\u09aa\u09a4\u09cd\u09b0|"
    r"\u098f\u09a8\u0986\u0987\u09a1\u09bf)"
)
NID_DIGITS = re.compile(
    r"(?<![\w\u0980-\u09ff])(?:[0-9\u09e6-\u09ef][ -]?){9,16}"
    r"[0-9\u09e6-\u09ef](?![\w\u0980-\u09ff])"
)
TRANSACTION_REFERENCE = re.compile(
    r"(?i)\b(?:txn\s*(?:id|no\.?|number)|transaction\s*(?:id|no\.?|number)|"
    r"order\s*(?:no\.?|number|id))\s*[:#-]?\s*(?:[A-Z0-9-]{1,})"
)
MAX_CUSTOM_PATTERN_SCAN = 20_000


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


def _replace_with_configured_value(_match: re.Match[str], *, replacement: str) -> str:
    return replacement


def _luhn_valid_card(match: re.Match[str]) -> str:
    translated = match.group().translate(CARD_DIGIT_TRANSLATION)
    digits = "".join(char for char in translated if char.isdigit())
    doubled = [
        int(digit) * (2 if index % 2 == len(digits) % 2 else 1)
        for index, digit in enumerate(digits)
    ]
    checksum = sum(value - 9 if value > 9 else value for value in doubled)
    if checksum % 10 == 0:
        return "[CARD REDACTED]"
    # Keep the established protection for an explicitly identified card
    # number, even when a synthetic or mistyped number fails its checksum.
    prefix = match.string[max(0, match.start() - 32) : match.start()]
    if re.search(r"(?i)(?:credit\s+)?card(?:\s+(?:number|no\.?))?\s*[:#-]?\s*$", prefix):
        return "[CARD REDACTED]"
    return match.group()


def _mask_nid_in_context(value: str) -> str:
    keywords = [match.span() for match in NID_KEYWORDS.finditer(value)]

    def replace_digits(match: re.Match[str]) -> str:
        start, end = match.span()
        if any(max(left - end, start - right) <= 80 for left, right in keywords):
            return "[NID]"
        return match.group()

    return NID_DIGITS.sub(replace_digits, value)


def mask_sensitive(value: str) -> str:
    """Mask common sensitive values before persistence; human review is still needed."""
    from .models import MaskingPattern

    prefix = value[:MAX_CUSTOM_PATTERN_SCAN]
    suffix = value[MAX_CUSTOM_PATTERN_SCAN:]
    for rule in MaskingPattern.objects.filter(is_active=True).only("pattern", "replacement")[:20]:
        try:
            replacement = rule.replacement
            prefix = re.sub(
                rule.pattern,
                partial(_replace_with_configured_value, replacement=replacement),
                prefix,
            )
        except re.error:
            # Invalid persisted patterns fail closed by being ignored.
            continue
    value = prefix + suffix
    # Mandatory detectors run after administrator rules so custom masking can
    # replace a complete token first, while built-in protections always run.
    value = EMAIL_ADDRESS.sub("[EMAIL]", value)
    value = _mask_nid_in_context(value)
    protected_references: dict[str, str] = {}

    def protect_reference(match: re.Match[str]) -> str:
        index = len(protected_references)
        letters = ""
        while index:
            index, remainder = divmod(index, 26)
            letters = chr(ord("a") + remainder) + letters
        marker = f"\u2063ref{letters or 'a'}\u2063"
        while marker in value or marker in protected_references:
            marker += "x"
        protected_references[marker] = match.group()
        return marker

    value = TRANSACTION_REFERENCE.sub(protect_reference, value)
    value = ACCOUNT_NUMBER.sub("[ACCOUNT_NUMBER]", value)
    value = PHONE_NUMBER.sub("[PHONE_NUMBER]", value)
    value = CARD_DIGITS.sub(_luhn_valid_card, value)
    value = SENTENCE_TEXT.sub(_mask_otp_in_sentence, value)
    for marker, reference in protected_references.items():
        value = value.replace(marker, reference)
    return value


def mask_extracted_text(value: str) -> str:
    """Mask text extracted from a text attachment before it can reach NLP."""
    return mask_sensitive(value)


def safe_original_text(value: str) -> str:
    """Retain reviewable original text while irreversibly removing OTPs and card numbers."""
    protected_references: dict[str, str] = {}

    def protect_reference(match: re.Match[str]) -> str:
        index = len(protected_references)
        letters = ""
        while index:
            index, remainder = divmod(index, 26)
            letters = chr(ord("a") + remainder) + letters
        marker = f"\u2063ref{letters or 'a'}\u2063"
        while marker in value or marker in protected_references:
            marker += "x"
        protected_references[marker] = match.group()
        return marker

    value = TRANSACTION_REFERENCE.sub(protect_reference, value)
    value = CARD_DIGITS.sub(_luhn_valid_card, value)
    value = SENTENCE_TEXT.sub(_mask_otp_in_sentence, value)
    for marker, reference in protected_references.items():
        value = value.replace(marker, reference)
    return value


MASKABLE_FIELDS = frozenset(
    {
        "title",
        "description",
        "acceptance_criteria",
        "environment",
        "steps_to_reproduce",
        "expected_result",
        "actual_result",
    }
)


def mask_sensitive_with_detections(value: str) -> tuple[str, list[str]]:
    """Return a review-safe masked copy and categories, never the original tokens."""
    masked = mask_sensitive(value)
    categories: list[str] = []
    markers = (
        ("[EMAIL]", "email"),
        ("[NID]", "nid"),
        ("[CARD REDACTED]", "card"),
        ("[ACCOUNT_NUMBER]", "account"),
        ("[PHONE_NUMBER]", "phone"),
        ("[OTP REDACTED]", "otp"),
    )
    for marker, category in markers:
        if marker in masked:
            categories.append(category)
    return masked, categories


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
    recurring = fields.get("recurring_of")
    if recurring:
        allowed = authorized_rows(user, Issue.objects.filter(status=IssueStatus.CLOSED))
        if not allowed.filter(pk=recurring.pk).exists() or (
            existing
            and (recurring.pk == existing.pk or recurring.created_at >= existing.created_at)
        ):
            raise ValidationError({"recurring_of": "Invalid closed request."})


def create_draft(user, fields: dict) -> Issue:
    organization = portal_organization(user)
    if not is_officer(user) or organization is None:
        raise PermissionDenied("Issue Officer role required.")
    with transaction.atomic():
        _validate_links(user, fields)
        issue = Issue.objects.create(organization=organization, created_by=user, **_clean(fields))
        from .models import IssueOriginalText

        IssueOriginalText.objects.create(
            issue=issue,
            title=safe_original_text(fields.get("title", "")),
            description=safe_original_text(fields.get("description", "")),
        )
        # BigAutoField uses the database sequence; this reference is immutable thereafter.
        issue.reference = f"SR-{issue.pk + 1023}"
        issue.save(update_fields=["reference", "updated_at"])
        from domains.search.embeddings import queue_issue_embedding

        queue_issue_embedding(issue)
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
        original_fields = {
            key: value for key, value in changes.items() if key in {"title", "description"}
        }
        for key, value in _clean(changes).items():
            setattr(locked, key, value)
        if original_fields:
            from .models import IssueOriginalText

            original, _ = IssueOriginalText.objects.get_or_create(issue=locked)
            for key, value in original_fields.items():
                setattr(original, key, safe_original_text(value))
            original.save(update_fields=[*original_fields, "updated_at"])
        locked.version += 1
        locked.save()
        if original_fields:
            from domains.search.embeddings import queue_issue_embedding

            queue_issue_embedding(locked)
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


def submit(user, issue: Issue, *, comment: str = "") -> Issue:
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
            details={"comment": mask_sensitive(comment.strip())} if comment.strip() else {},
        )
        from domains.search.embeddings import queue_issue_embedding

        queue_issue_embedding(locked)
        notify_issue_event(event)
    return locked
