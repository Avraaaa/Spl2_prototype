"""EX-04 / N-04: first-login password flow, temporary credential expiry, reset replay,
deactivation and session login behaviour."""

from datetime import timedelta

import pytest
from django.utils import timezone

from domains.accounts import services

from .conftest import PASSWORD, client_for, login

pytestmark = pytest.mark.django_db
NEW_PASSWORD = "Fresh-Strong-Pass-2026"


def _new_user(admin, bank):
    response = client_for(admin).post(
        "/api/admin/users/",
        {
            "username": "first_login",
            "email": "f@example.test",
            "full_name": "First Login",
            "organization": bank.id,
            "roles": ["ISSUE_OFFICER"],
        },
        format="json",
    )
    assert response.status_code == 201
    return response.json()["temporary_password"]


def test_login_logout_and_me(officer_a, bank_a):
    client, response = login("officer_a")
    assert response.status_code == 200
    me = client.get("/api/auth/me/")
    assert me.status_code == 200
    assert me.json()["username"] == "officer_a"
    assert me.json()["organization"] == {
        "id": bank_a.id,
        "name": bank_a.name,
        "code": "NWD",
        "kind": "BANK",
    }
    assert client.post("/api/auth/logout/").status_code == 204
    assert client.get("/api/auth/me/").status_code in (401, 403)


def test_wrong_password_is_generic_401(officer_a):
    _, response = login("officer_a", "wrong-password")
    assert response.status_code == 401
    _, unknown = login("nobody", "wrong-password")
    assert unknown.status_code == 401
    assert response.json() == unknown.json()


def test_forced_password_change_gates_other_api(admin, bank_a):
    temp = _new_user(admin, bank_a)
    client, response = login("first_login", temp)
    assert response.status_code == 200
    assert response.json()["must_change_password"] is True
    # Only me / change-password / logout are reachable before the change.
    assert client.get("/api/auth/me/").status_code == 200
    blocked = client.get("/api/admin/users/")
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "password_change_required"

    weak = client.post(
        "/api/auth/change-password/",
        {"current_password": temp, "new_password": "123"},
        format="json",
    )
    assert weak.status_code == 400
    ok = client.post(
        "/api/auth/change-password/",
        {"current_password": temp, "new_password": NEW_PASSWORD},
        format="json",
    )
    assert ok.status_code == 200
    assert client.get("/api/auth/me/").json()["must_change_password"] is False

    # Replay: the temporary credential no longer works.
    _, replay = login("first_login", temp)
    assert replay.status_code == 401
    _, fresh = login("first_login", NEW_PASSWORD)
    assert fresh.status_code == 200


def test_expired_temporary_credential_is_rejected(admin, bank_a):
    temp = _new_user(admin, bank_a)
    from django.contrib.auth.models import User

    account = User.objects.get(username="first_login").account
    account.temporary_password_expires_at = timezone.now() - timedelta(seconds=1)
    account.save()
    _, response = login("first_login", temp)
    assert response.status_code == 401
    assert response.json()["code"] == "temporary_credential_expired"


def test_admin_reset_issues_new_temp_and_invalidates_old_password(admin, officer_a):
    response = client_for(admin).post(f"/api/admin/users/{officer_a.id}/reset-password/")
    assert response.status_code == 200
    temp = response.json()["temporary_password"]
    _, old = login("officer_a", PASSWORD)
    assert old.status_code == 401
    client, new = login("officer_a", temp)
    assert new.status_code == 200 and new.json()["must_change_password"] is True


def test_support_cannot_reset_or_deactivate(support, officer_a):
    client = client_for(support)
    assert client.post(f"/api/admin/users/{officer_a.id}/reset-password/").status_code == 403
    assert client.post(f"/api/admin/users/{officer_a.id}/deactivate/").status_code == 403


def test_deactivated_user_loses_live_session_and_login(admin, officer_a):
    session, _ = login("officer_a")
    assert session.get("/api/auth/me/").status_code == 200
    assert client_for(admin).post(f"/api/admin/users/{officer_a.id}/deactivate/").status_code == 200
    assert session.get("/api/auth/me/").status_code in (401, 403)
    _, again = login("officer_a")
    assert again.status_code == 401


def test_admin_cannot_deactivate_self(admin):
    assert client_for(admin).post(f"/api/admin/users/{admin.id}/deactivate/").status_code == 400


def test_password_change_requires_current_password(officer_a):
    client, _ = login("officer_a")
    bad = client.post(
        "/api/auth/change-password/",
        {"current_password": "nope", "new_password": NEW_PASSWORD},
        format="json",
    )
    assert bad.status_code == 400


def test_login_is_rate_limited(officer_a, settings):
    statuses = [
        login("officer_a", "wrong")[1].status_code
        for _ in range(services.LOGIN_RATE_PER_MINUTE + 1)
    ]
    assert statuses[-1] == 429
