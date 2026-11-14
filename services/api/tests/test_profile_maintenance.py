"""P1-T1b / N-01: self-service profile and username changes."""

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction

from domains.accounts.models import AccountEvent

from .conftest import PASSWORD, client_for, login

pytestmark = pytest.mark.django_db


def test_profile_updates_only_the_authenticated_user(officer_a, officer_b, bank_a, bank_b):
    client = client_for(officer_a)
    response = client.patch(
        "/api/auth/me/",
        {"full_name": "Updated Officer", "email": "updated@example.test"},
        format="json",
    )
    assert response.status_code == 200, response.content
    assert response.json()["full_name"] == "Updated Officer"
    assert response.json()["email"] == "updated@example.test"
    assert response.json()["organization"]["id"] == bank_a.id
    officer_a.refresh_from_db()
    officer_a.account.refresh_from_db()
    officer_b.refresh_from_db()
    assert officer_a.account.full_name == "Updated Officer"
    assert officer_a.email == "updated@example.test"
    assert officer_b.email == "officer_b@example.test"
    assert officer_b.account.organization_id == bank_b.id
    event = AccountEvent.objects.get(subject=officer_a, kind="PROFILE_UPDATED")
    assert event.actor_id == officer_a.id
    assert event.details == {
        "full_name": {"old": "Officer_A", "new": "Updated Officer"},
        "email": {"old": "officer_a@example.test", "new": "updated@example.test"},
    }


@pytest.mark.parametrize(
    "field", ["organization", "roles", "is_active", "username", "id", "password"]
)
def test_profile_rejects_protected_fields(officer_a, officer_b, bank_b, field):
    value = {
        "organization": bank_b.id,
        "roles": ["DATASOFT_ADMIN"],
        "is_active": False,
        "username": officer_b.username,
        "id": officer_b.id,
        "password": "hijacked",
    }[field]
    response = client_for(officer_a).patch(
        "/api/auth/me/", {"full_name": "Hijack", field: value}, format="json"
    )
    assert response.status_code == 400
    officer_a.refresh_from_db()
    officer_a.account.refresh_from_db()
    assert officer_a.account.full_name == "Officer_A"
    assert not AccountEvent.objects.filter(subject=officer_a, kind="PROFILE_UPDATED").exists()


def test_profile_validation_and_noop_do_not_append_events(officer_a):
    client = client_for(officer_a)
    assert client.patch("/api/auth/me/", {"full_name": "   "}, format="json").status_code == 400
    assert client.patch("/api/auth/me/", {"email": "bad"}, format="json").status_code == 400
    assert client.patch("/api/auth/me/", ["invalid"], format="json").status_code == 400
    assert (
        client.patch("/api/auth/me/", {"full_name": "Officer_A"}, format="json").status_code == 200
    )
    assert not AccountEvent.objects.filter(subject=officer_a, kind="PROFILE_UPDATED").exists()


def test_profile_ignores_forged_tenant_and_target_identity(officer_a, officer_b, bank_a, bank_b):
    response = client_for(officer_a).patch(
        f"/api/auth/me/?user_id={officer_b.pk}&organization={bank_b.pk}",
        {"email": "owned@example.test"},
        format="json",
        HTTP_X_ORGANIZATION_ID=str(bank_b.pk),
        HTTP_X_USER_ID=str(officer_b.pk),
    )
    assert response.status_code == 200
    assert response.json()["organization"]["id"] == bank_a.pk
    officer_b.refresh_from_db()
    assert officer_b.email == "officer_b@example.test"
    assert not AccountEvent.objects.filter(subject=officer_b, kind="PROFILE_UPDATED").exists()


def test_username_change_requires_password_and_is_case_insensitive(officer_a, officer_b):
    client = client_for(officer_a)
    endpoint = "/api/auth/change-username/"
    for username, password in [
        ("officer_b", "wrong"),
        ("OFFICER_B", PASSWORD),
        ("bad name", PASSWORD),
        ("bad\n", PASSWORD),
        ("ab", PASSWORD),
    ]:
        response = client.post(
            endpoint, {"username": username, "current_password": password}, format="json"
        )
        assert response.status_code == 400, response.content
    assert client.post(endpoint, ["invalid"], format="json").status_code == 400
    officer_a.refresh_from_db()
    assert officer_a.username == "officer_a"
    assert not AccountEvent.objects.filter(subject=officer_a, kind="USERNAME_CHANGED").exists()

    response = client.post(
        endpoint, {"username": "New_Officer", "current_password": PASSWORD}, format="json"
    )
    assert response.status_code == 200, response.content
    assert response.json()["username"] == "New_Officer"
    event = AccountEvent.objects.get(subject=officer_a, kind="USERNAME_CHANGED")
    assert event.actor_id == officer_a.id
    assert event.details == {"username": {"old": "officer_a", "new": "New_Officer"}}
    assert "current_password" not in str(event.details)
    assert officer_b.username == "officer_b"


def test_username_uniqueness_is_enforced_in_database(officer_a, officer_b):
    with pytest.raises(IntegrityError), transaction.atomic():
        officer_a.username = "OFFICER_B"
        officer_a.save(update_fields=["username"])


def test_username_noop_and_case_only_change(officer_a):
    client = client_for(officer_a)
    endpoint = "/api/auth/change-username/"
    unchanged = client.post(
        endpoint, {"username": "officer_a", "current_password": PASSWORD}, format="json"
    )
    assert unchanged.status_code == 200
    assert not AccountEvent.objects.filter(subject=officer_a, kind="USERNAME_CHANGED").exists()
    changed = client.post(
        endpoint, {"username": "OFFICER_A", "current_password": PASSWORD}, format="json"
    )
    assert changed.status_code == 200, changed.content
    assert changed.json()["username"] == "OFFICER_A"
    assert AccountEvent.objects.get(subject=officer_a, kind="USERNAME_CHANGED").details == {
        "username": {"old": "officer_a", "new": "OFFICER_A"}
    }


def test_profile_and_username_gate_and_anonymous_access(officer_a, bank_a, make_user):
    pending = make_user("pending_profile", bank_a, "ISSUE_OFFICER", active_password=False)
    pending.set_password(PASSWORD)
    pending.save(update_fields=["password"])
    for client in (client_for(), client_for(pending)):
        assert client.patch("/api/auth/me/", {"full_name": "No"}, format="json").status_code in (
            401,
            403,
        )
        assert client.post(
            "/api/auth/change-username/",
            {"username": "other_name", "current_password": PASSWORD},
            format="json",
        ).status_code in (401, 403)
    assert client_for(officer_a).get("/api/admin/users/").status_code == 403


def test_profile_and_username_reject_user_without_portal_account(db):
    bare = User.objects.create_user(username="bare_user", password=PASSWORD)
    client = client_for(bare)
    assert (
        client.patch("/api/auth/me/", {"email": "bare@example.test"}, format="json").status_code
        == 403
    )
    assert (
        client.post(
            "/api/auth/change-username/",
            {"username": "bare_renamed", "current_password": PASSWORD},
            format="json",
        ).status_code
        == 403
    )


def test_deactivated_user_cannot_edit_profile_or_username(officer_a):
    officer_a.is_active = False
    officer_a.save(update_fields=["is_active"])
    client = client_for(officer_a)
    assert (
        client.patch("/api/auth/me/", {"full_name": "Should Not Change"}, format="json").status_code
        == 403
    )
    assert (
        client.post(
            "/api/auth/change-username/",
            {"username": "should_not_change", "current_password": PASSWORD},
            format="json",
        ).status_code
        == 403
    )
    officer_a.refresh_from_db()
    officer_a.account.refresh_from_db()
    assert officer_a.username == "officer_a"
    assert officer_a.account.full_name == "Officer_A"


def test_session_survives_username_change_and_new_login_works(officer_a):
    session, response = login("officer_a")
    assert response.status_code == 200
    changed = session.post(
        "/api/auth/change-username/",
        {"username": "renewed_officer", "current_password": PASSWORD},
        format="json",
    )
    assert changed.status_code == 200, changed.content
    assert session.get("/api/auth/me/").json()["username"] == "renewed_officer"
    assert login("renewed_officer")[1].status_code == 200
    assert login("officer_a")[1].status_code == 401
    assert User.objects.get(pk=officer_a.pk).username == "renewed_officer"
