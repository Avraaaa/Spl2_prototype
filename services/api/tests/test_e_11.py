"""Configurable masking rules stay tenant independent and preserve safe defaults."""

from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from domains.issues.models import Issue, IssueStatus, MaskingPattern
from domains.issues.services import mask_sensitive, safe_original_text

from .conftest import client_for

pytestmark = pytest.mark.django_db


def test_active_custom_pattern_masks_and_disabled_pattern_does_not():
    pattern = MaskingPattern.objects.create(
        name="Synthetic employee token", pattern=r"EMP-[0-9]{5}", replacement="[EMPLOYEE]"
    )
    assert "[EMPLOYEE]" in mask_sensitive("Reference EMP-12345")
    pattern.is_active = False
    pattern.save(update_fields=["is_active"])
    assert "EMP-12345" in mask_sensitive("Reference EMP-12345")


def test_builtin_otp_and_card_rules_cannot_be_disabled():
    assert "[OTP REDACTED]" in mask_sensitive("OTP 123456")
    assert "[CARD REDACTED]" in mask_sensitive("Card 4111 1111 1111 1111")


def test_restricted_original_copy_never_retains_otp_or_full_card():
    original = safe_original_text("OTP 123456; card 4111 1111 1111 1111")
    assert "123456" not in original
    assert "4111 1111 1111 1111" not in original


def test_admin_can_create_and_disable_custom_pattern(admin, support):
    admin_client = client_for(admin)
    created = admin_client.post(
        "/api/issues/masking-patterns/",
        {"name": "Synthetic code", "pattern": r"CODE-[0-9]{4}", "replacement": "[CODE]"},
        format="json",
    )
    assert created.status_code == 201
    assert "[CODE]" in mask_sensitive("CODE-1234")
    assert (
        client_for(support)
        .post(
            "/api/issues/masking-patterns/",
            {"name": "No permission", "pattern": "secret"},
            format="json",
        )
        .status_code
        == 403
    )
    disabled = admin_client.patch(
        f"/api/issues/masking-patterns/{created.json()['id']}/",
        {"is_active": False},
        format="json",
    )
    assert disabled.status_code == 200
    assert "CODE-1234" in mask_sensitive("CODE-1234")


def test_text_attachment_is_masked_before_nlp(admin, officer_a):
    issue = Issue.objects.create(
        organization=officer_a.account.organization,
        created_by=officer_a,
        status=IssueStatus.SUBMITTED,
        reference="SR-99101",
        title="Synthetic issue",
    )
    raw = b"OTP 123456; card 4111 1111 1111 1111; EMP-12345"
    MaskingPattern.objects.create(
        name="Synthetic employee token", pattern=r"EMP-[0-9]{5}", replacement="[EMPLOYEE]"
    )
    with patch("domains.search.services._ml_embeddings", return_value=None) as embed:
        response = client_for(officer_a).post(
            f"/api/issues/{issue.pk}/attachments/",
            {"file": SimpleUploadedFile("trace.txt", raw, content_type="text/plain")},
            format="multipart",
        )
    assert response.status_code == 201
    embed.assert_called_once()
    indexed_text = embed.call_args.args[0][0]
    assert "123456" not in indexed_text
    assert "4111 1111 1111 1111" not in indexed_text
    assert "EMP-12345" not in indexed_text
    assert "[EMPLOYEE]" in indexed_text


def test_custom_patterns_are_rejected_when_unsafe_or_too_long(admin):
    api = client_for(admin)
    for pattern in ("(", "a" * 201, r"(a+)+$"):
        response = api.post(
            "/api/issues/masking-patterns/",
            {"name": f"Invalid {len(pattern)}", "pattern": pattern},
            format="json",
        )
        assert response.status_code == 400


def test_active_custom_pattern_count_is_capped(admin):
    api = client_for(admin)
    for index in range(20):
        MaskingPattern.objects.create(name=f"rule-{index}", pattern=f"TOKEN-{index}")
    response = api.post(
        "/api/issues/masking-patterns/",
        {"name": "rule-over-limit", "pattern": "TOKEN-X"},
        format="json",
    )
    assert response.status_code == 400


def test_custom_rules_scan_only_bounded_prefix(monkeypatch):
    calls = []
    original = __import__("re").sub

    def track(pattern, repl, value, *args, **kwargs):
        if pattern == "TOKEN":
            calls.append(len(value))
        return original(pattern, repl, value, *args, **kwargs)

    monkeypatch.setattr("domains.issues.services.re.sub", track)
    MaskingPattern.objects.create(name="token", pattern="TOKEN")
    mask_sensitive("x" * 30000)
    assert calls and max(calls) <= 20000
