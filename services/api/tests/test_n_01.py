"""N-01/N-02/EX-04: only the DataSoft Administrator registers banks and creates accounts."""

import logging

import pytest

from domains.accounts.models import AccountEvent

from .conftest import client_for, login

pytestmark = pytest.mark.django_db

NEW_USER = {
    "username": "new_officer",
    "email": "new.officer@example.test",
    "full_name": "New Officer",
    "roles": ["ISSUE_OFFICER"],
}


def test_anonymous_cannot_use_admin_api(bank_a):
    client = client_for()
    assert client.get("/api/admin/users/").status_code in (401, 403)
    assert client.post(
        "/api/admin/users/", {**NEW_USER, "organization": bank_a.id}, format="json"
    ).status_code in (401, 403)
    assert client.post(
        "/api/admin/organizations/", {"name": "X", "code": "X"}, format="json"
    ).status_code in (401, 403)


@pytest.mark.parametrize("who", ["support", "officer_a"])
def test_non_admins_cannot_create_users_or_banks(request, who, bank_a):
    client = client_for(request.getfixturevalue(who))
    assert (
        client.post(
            "/api/admin/users/", {**NEW_USER, "organization": bank_a.id}, format="json"
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/admin/organizations/", {"name": "X Bank", "code": "XB"}, format="json"
        ).status_code
        == 403
    )
    assert client.get("/api/admin/users/").status_code == 403


def test_admin_registers_bank_and_creates_user_with_temporary_credential(admin, caplog):
    client = client_for(admin)
    caplog.set_level(logging.DEBUG)
    org = client.post(
        "/api/admin/organizations/", {"name": "Lakeside Demo Bank", "code": "LKD"}, format="json"
    )
    assert org.status_code == 201, org.content
    assert org.json()["kind"] == "BANK"

    created = client.post(
        "/api/admin/users/", {**NEW_USER, "organization": org.json()["id"]}, format="json"
    )
    assert created.status_code == 201, created.content
    body = created.json()
    temp = body["temporary_password"]
    assert len(temp) >= 12
    assert body["user"]["must_change_password"] is True
    assert body["user"]["roles"] == ["ISSUE_OFFICER"]
    # Temporary credential is stored hashed and never logged.
    from django.contrib.auth.models import User

    stored = User.objects.get(username="new_officer")
    assert temp not in stored.password and stored.check_password(temp)
    assert temp not in caplog.text
    assert AccountEvent.objects.filter(subject=stored, kind="USER_CREATED", actor=admin).exists()


def test_no_public_registration_endpoint():
    assert client_for().post("/api/auth/register/", {}, format="json").status_code == 404


def test_role_must_fit_organization_kind(admin, bank_a, datasoft):
    client = client_for(admin)
    bad_bank = client.post(
        "/api/admin/users/",
        {**NEW_USER, "organization": bank_a.id, "roles": ["SUPPORT_AGENT"]},
        format="json",
    )
    assert bad_bank.status_code == 400
    bad_ds = client.post(
        "/api/admin/users/",
        {**NEW_USER, "organization": datasoft.id, "roles": ["ISSUE_OFFICER"]},
        format="json",
    )
    assert bad_ds.status_code == 400
    exclusive = client.post(
        "/api/admin/users/",
        {**NEW_USER, "organization": datasoft.id, "roles": ["DATASOFT_ADMIN", "SUPPORT_AGENT"]},
        format="json",
    )
    assert exclusive.status_code == 400
    empty = client.post(
        "/api/admin/users/", {**NEW_USER, "organization": bank_a.id, "roles": []}, format="json"
    )
    assert empty.status_code == 400


def test_dual_officer_and_verifier_membership(admin, bank_a):
    client = client_for(admin)
    created = client.post(
        "/api/admin/users/",
        {**NEW_USER, "organization": bank_a.id, "roles": ["ISSUE_OFFICER", "ISSUE_VERIFIER"]},
        format="json",
    )
    assert created.status_code == 201
    temp = created.json()["temporary_password"]
    session, response = login("new_officer", temp)
    assert response.status_code == 200
    session.post(
        "/api/auth/change-password/",
        {"current_password": temp, "new_password": "Another-Strong-Pass-77"},
        format="json",
    )
    me = session.get("/api/auth/me/").json()
    assert sorted(me["roles"]) == ["ISSUE_OFFICER", "ISSUE_VERIFIER"]
    assert me["organization"]["id"] == bank_a.id


def test_admin_replaces_roles(admin, officer_a):
    client = client_for(admin)
    response = client.put(
        f"/api/admin/users/{officer_a.id}/roles/", {"roles": ["ISSUE_VERIFIER"]}, format="json"
    )
    assert response.status_code == 200
    assert response.json()["roles"] == ["ISSUE_VERIFIER"]
    assert (
        client.put(
            f"/api/admin/users/{officer_a.id}/roles/", {"roles": ["DATASOFT_ADMIN"]}, format="json"
        ).status_code
        == 400
    )
