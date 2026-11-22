from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from domains.accounts.models import AccountEvent
from domains.notifications.models import OutboxMessage


@pytest.mark.django_db
def test_new_org_without_contact_email_is_flagged_for_admin(admin):
    client = APIClient()
    client.force_authenticate(admin)
    missing = client.post(
        "/api/admin/organizations/",
        {"name": "No Email Co", "code": "NOE"},
        format="json",
    )
    assert missing.status_code == 201
    assert missing.data["contact_email"] == ""
    assert missing.data["contact_email_placeholder"] is True
    created = client.post(
        "/api/admin/organizations/",
        {"name": "Contoso Demo", "code": "CTD", "contact_email": "contact@contoso.example"},
        format="json",
    )
    assert created.status_code == 201
    assert created.data["contact_email_placeholder"] is False


@pytest.mark.django_db
def test_configured_email_hides_password_and_queues_it_for_registered_email(admin, bank_a, caplog):
    client = APIClient()
    client.force_authenticate(admin)
    with override_settings(
        EMAIL_DELIVERY_CONFIGURED=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    ):
        response = client.post(
            "/api/admin/users/",
            {
                "organization": bank_a.pk,
                "username": "new_member",
                "email": "member@example.test",
                "full_name": "Member",
                "roles": ["ISSUE_OFFICER"],
            },
            format="json",
        )
        assert response.status_code == 201
        assert "temporary_password" not in response.data
        assert response.data["delivery"] == "email"
        message = OutboxMessage.objects.get(recipient__username="new_member", channel="email")
        assert message.payload["to"] == "member@example.test"
        assert "temporary_password" not in message.payload
        assert message.status == "pending"
        assert "temporary_password" not in caplog.text
        message.status = OutboxMessage.Status.FAILED
        message.save(update_fields=["status"])
        pending = client.get(f"/api/admin/users/{response.data['user']['id']}/")
        assert pending.data["credentials_pending"] is True
        reset = client.post(
            f"/api/admin/users/{response.data['user']['id']}/reset-password/", format="json"
        )
        assert reset.status_code == 200
        assert "temporary_password" not in reset.data
        assert reset.data["delivery"] == "email"


@pytest.mark.django_db
def test_console_fallback_returns_temporary_secret(admin, bank_a):
    client = APIClient()
    client.force_authenticate(admin)
    with override_settings(EMAIL_DELIVERY_CONFIGURED=False):
        response = client.post(
            "/api/admin/users/",
            {
                "organization": bank_a.pk,
                "username": "console_user",
                "email": "console@example.test",
                "full_name": "Console",
                "roles": ["ISSUE_OFFICER"],
            },
            format="json",
        )
        assert response.data["delivery"] == "console"
        assert response.data["temporary_password"]
        assert "temporary_password" in response.data
        reset = client.post(
            f"/api/admin/users/{response.data['user']['id']}/reset-password/",
            format="json",
        )
        assert reset.status_code == 200
        assert reset.data["delivery"] == "console"
        assert reset.data["temporary_password"]


@pytest.mark.django_db
def test_forgot_password_is_generic_single_use_and_invalidated_by_later_reset(officer_a, settings):
    settings.PASSWORD_RESET_RATE_PER_MINUTE = 50
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["password_reset"] = "50/min"
    client = APIClient()
    first = client.post("/api/auth/forgot-password/", {"email": officer_a.email}, format="json")
    unknown = client.post(
        "/api/auth/forgot-password/",
        {"email": "missing@example.test"},
        format="json",
    )
    assert first.status_code == unknown.status_code == 202
    assert first.data == unknown.data
    queued = OutboxMessage.objects.get(
        recipient=officer_a, idempotency_key__startswith="password-reset:"
    )
    from urllib.parse import parse_qs, urlparse

    from domains.accounts.models import PasswordResetToken

    params = parse_qs(urlparse(queued.payload["body"].splitlines()[-1]).query)
    token, uid = params["token"][0], params["uid"][0]
    assert PasswordResetToken.objects.get(user=officer_a).token_hash != token
    reset_again = client.post(
        "/api/auth/forgot-password/", {"email": officer_a.email}, format="json"
    )
    assert reset_again.status_code == 202
    stale = client.post(
        "/api/auth/reset-password/",
        {"uid": uid, "token": token, "password": "Changed-Synthetic-2026!"},
        format="json",
    )
    assert stale.status_code == 400
    latest = OutboxMessage.objects.filter(
        recipient=officer_a, idempotency_key__startswith="password-reset:"
    ).latest("id")
    params = parse_qs(urlparse(latest.payload["body"].splitlines()[-1]).query)
    latest_token, latest_uid = params["token"][0], params["uid"][0]
    success = client.post(
        "/api/auth/reset-password/",
        {"uid": latest_uid, "token": latest_token, "password": "Changed-Synthetic-2026!"},
        format="json",
    )
    assert success.status_code == 204
    replay = client.post(
        "/api/auth/reset-password/",
        {"uid": latest_uid, "token": latest_token, "password": "Changed-Synthetic-2026!"},
        format="json",
    )
    assert replay.status_code == 400
    assert AccountEvent.objects.filter(subject=officer_a, kind="PASSWORD_RESET_COMPLETED").exists()


@pytest.mark.django_db
def test_reset_token_expiry_and_throttle(settings, officer_a):
    settings.PASSWORD_RESET_TTL_MINUTES = 30
    settings.PASSWORD_RESET_RATE_PER_MINUTE = 1
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["password_reset"] = "1/min"
    client = APIClient()
    assert (
        client.post(
            "/api/auth/forgot-password/", {"email": officer_a.email}, format="json"
        ).status_code
        == 202
    )
    assert (
        client.post(
            "/api/auth/forgot-password/", {"email": officer_a.email}, format="json"
        ).status_code
        == 429
    )
    from urllib.parse import parse_qs, urlparse

    from domains.accounts.models import PasswordResetToken

    settings.PASSWORD_RESET_RATE_PER_MINUTE = 20
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["password_reset"] = "20/min"
    queued = OutboxMessage.objects.filter(
        recipient=officer_a, idempotency_key__startswith="password-reset:"
    ).latest("id")
    params = parse_qs(urlparse(queued.payload["body"].splitlines()[-1]).query)
    PasswordResetToken.objects.filter(pk=int(params["uid"][0].split(".")[1])).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    expired = client.post(
        "/api/auth/reset-password/",
        {
            "uid": params["uid"][0],
            "token": params["token"][0],
            "password": "Changed-Synthetic-2026!",
        },
        format="json",
    )
    assert expired.status_code == 400


@pytest.mark.django_db
def test_resend_settings_and_test_email_command(settings):
    settings.RESEND_API_KEY = "re_test_synthetic"
    settings.EMAIL_FROM = "portal@example.test"
    settings.EMAIL_REPLY_TO = "help@example.test"
    from io import StringIO

    from django.core.mail import get_connection
    from django.core.management import call_command
    from django.test import override_settings

    with override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="smtp.resend.com",
        EMAIL_PORT=587,
        EMAIL_HOST_USER="resend",
        EMAIL_HOST_PASSWORD="re_test_synthetic",
    ):
        connection = get_connection()
        assert connection.host == "smtp.resend.com"
        assert connection.port == 587
        assert connection.username == "resend"
        assert connection.password == "re_test_synthetic"
    with override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
        call_command("send_test_email", "--to", "recipient@example.test", stdout=StringIO())
