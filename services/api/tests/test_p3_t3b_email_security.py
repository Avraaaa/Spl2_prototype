import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from domains.accounts.models import PasswordResetToken
from domains.notifications.models import OutboxMessage


@pytest.mark.django_db
def test_outbox_scrubs_setup_credential_after_success(admin, bank_a):
    from domains.accounts.services import create_user
    from domains.notifications.worker import process_due

    with override_settings(
        EMAIL_DELIVERY_CONFIGURED=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    ):
        user, temporary = create_user(
            admin,
            organization=bank_a,
            username="setup_success",
            email="setup-success@example.test",
            full_name="Setup Success",
            roles=["ISSUE_OFFICER"],
        )
    message = OutboxMessage.objects.get(recipient=user)
    assert "#token=" in message.payload["body"]
    assert temporary not in message.payload["body"]
    assert PasswordResetToken.objects.filter(user=user).exists()
    with override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
        assert process_due(limit=1) == 1
    message.refresh_from_db()
    assert message.status == OutboxMessage.Status.SENT
    assert message.payload["subject"]
    assert message.payload["body"] == "[REDACTED AFTER DELIVERY]"
    assert message.payload["html"] == "[REDACTED AFTER DELIVERY]"


@pytest.mark.django_db
def test_outbox_scrubs_setup_credential_after_terminal_failure(
    admin, bank_a, settings, monkeypatch
):
    from domains.accounts.services import create_user
    from domains.notifications import worker

    with override_settings(EMAIL_DELIVERY_CONFIGURED=True):
        user, temporary = create_user(
            admin,
            organization=bank_a,
            username="setup_failure",
            email="setup-failure@example.test",
            full_name="Setup Failure",
            roles=["ISSUE_OFFICER"],
        )
    message = OutboxMessage.objects.get(
        recipient=user, idempotency_key__startswith="account-created:"
    )
    assert "#token=" in message.payload["body"]
    assert temporary not in message.payload["body"]
    settings.OUTBOX_MAX_ATTEMPTS = 1

    def fail_send(*args, **kwargs):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(worker.EmailMultiAlternatives, "send", fail_send)
    assert worker.process_due(limit=1) == 1
    message.refresh_from_db()
    assert message.status == OutboxMessage.Status.DEAD
    assert message.payload["body"] == "[REDACTED AFTER DELIVERY]"
    assert message.payload["html"] == "[REDACTED AFTER DELIVERY]"


@pytest.mark.django_db
def test_forgot_password_throttles_by_normalized_email(officer_a, settings):
    settings.PASSWORD_RESET_RATE_PER_MINUTE = 1
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["password_reset"] = "50/min"
    client = APIClient()
    first = client.post("/api/auth/forgot-password/", {"email": officer_a.email}, format="json")
    same_email = client.post(
        "/api/auth/forgot-password/",
        {"email": f" {officer_a.email.upper()} "},
        format="json",
    )
    other_email = client.post(
        "/api/auth/forgot-password/", {"email": "other@example.test"}, format="json"
    )
    assert first.status_code == 202
    assert same_email.status_code == 429
    assert other_email.status_code == 202


@pytest.mark.django_db
def test_reset_api_rejects_get_token_use(officer_a):
    response = APIClient().get("/api/auth/reset-password/", {"uid": "1.1", "token": "synthetic"})
    assert response.status_code == 405
    assert OutboxMessage.objects.filter(recipient=officer_a).count() == 0


@pytest.mark.django_db
def test_organization_placeholder_recomputed_on_contact_email_save(admin, bank_a):
    client = APIClient()
    client.force_authenticate(admin)
    url = f"/api/admin/organizations/{bank_a.pk}/contact-email/"
    empty = client.patch(url, {"contact_email": ""}, format="json")
    assert empty.status_code == 200
    assert empty.data["contact_email_placeholder"] is True
    populated = client.patch(url, {"contact_email": "contact@example.test"}, format="json")
    assert populated.status_code == 200
    assert populated.data["contact_email_placeholder"] is False
