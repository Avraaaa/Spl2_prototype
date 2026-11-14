"""Invariant 11: CSRF is enforced on session login, logout and password change;
temporary-credential expiry is enforced at password change too (review findings P1-T1)."""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from .conftest import PASSWORD, client_for

pytestmark = pytest.mark.django_db
CREDS = {"username": "officer_a", "password": PASSWORD}


def _csrf_client() -> tuple[APIClient, str]:
    client = APIClient(enforce_csrf_checks=True)
    assert client.get("/api/auth/csrf/").status_code == 204
    return client, client.cookies["csrftoken"].value


def test_login_requires_csrf_token(officer_a):
    client, token = _csrf_client()
    assert client.post("/api/auth/login/", CREDS, format="json").status_code == 403
    assert (
        client.post(
            "/api/auth/login/", CREDS, format="json", HTTP_X_CSRFTOKEN="bogus" * 6
        ).status_code
        == 403
    )
    assert (
        client.post("/api/auth/login/", CREDS, format="json", HTTP_X_CSRFTOKEN=token).status_code
        == 200
    )


def test_logout_and_password_change_require_csrf(officer_a):
    client, token = _csrf_client()
    assert (
        client.post("/api/auth/login/", CREDS, format="json", HTTP_X_CSRFTOKEN=token).status_code
        == 200
    )
    token = client.cookies["csrftoken"].value  # rotated on login
    body = {"current_password": PASSWORD, "new_password": "Brand-New-Pass-2026"}
    assert client.post("/api/auth/change-password/", body, format="json").status_code == 403
    assert client.post("/api/auth/logout/").status_code == 403
    assert client.get("/api/auth/me/").status_code == 200  # session survived the forged logout
    assert client.post("/api/auth/logout/", HTTP_X_CSRFTOKEN=token).status_code == 204
    assert client.get("/api/auth/me/").status_code in (401, 403)


def test_logout_without_session_is_idempotent():
    assert APIClient().post("/api/auth/logout/").status_code == 204


def test_change_password_rejected_after_temporary_expiry(admin, bank_a):
    created = (
        client_for(admin)
        .post(
            "/api/admin/users/",
            {
                "username": "late_user",
                "email": "l@example.test",
                "full_name": "Late User",
                "organization": bank_a.id,
                "roles": ["ISSUE_OFFICER"],
            },
            format="json",
        )
        .json()
    )
    temp = created["temporary_password"]
    client = APIClient()
    assert (
        client.post(
            "/api/auth/login/", {"username": "late_user", "password": temp}, format="json"
        ).status_code
        == 200
    )
    from django.contrib.auth.models import User

    account = User.objects.get(username="late_user").account
    account.temporary_password_expires_at = timezone.now() - timedelta(seconds=1)
    account.save()
    response = client.post(
        "/api/auth/change-password/",
        {"current_password": temp, "new_password": "Brand-New-Pass-2026"},
        format="json",
    )
    assert response.status_code == 400
    assert "expired" in str(response.json()).lower()
    assert User.objects.get(username="late_user").account.must_change_password is True
