"""EX-01 (P1 scope): membership and organization APIs never leak across banks.
Issue/attachment/search/export negative tests are added when those domains exist (P2+)."""

import pytest

from .conftest import client_for

pytestmark = pytest.mark.django_db


def test_me_reports_only_own_bank(officer_a, officer_b, bank_a, bank_b):
    me_a = client_for(officer_a).get("/api/auth/me/").json()
    assert me_a["organization"]["id"] == bank_a.id
    assert bank_b.name not in str(me_a)


def test_bank_users_cannot_enumerate_users_or_orgs(officer_a, officer_b, bank_b):
    client = client_for(officer_a)
    assert client.get("/api/admin/users/").status_code == 403
    assert client.get(f"/api/admin/users/{officer_b.id}/").status_code == 403
    assert client.get("/api/admin/organizations/").status_code == 403
    assert client.get(f"/api/admin/organizations/{bank_b.id}/").status_code in (403, 404, 405)


def test_bank_spoofing_headers_and_query_are_ignored(officer_a, bank_a, bank_b):
    client = client_for(officer_a)
    me = client.get(
        f"/api/auth/me/?organization={bank_b.id}", HTTP_X_ORGANIZATION_ID=str(bank_b.id)
    ).json()
    assert me["organization"]["id"] == bank_a.id


def test_admin_sees_all_organizations_and_users(admin, officer_a, officer_b, bank_a, bank_b):
    client = client_for(admin)
    orgs = {o["code"] for o in client.get("/api/admin/organizations/").json()}
    assert {"NWD", "RSD", "DATASOFT"} <= orgs
    users = client.get(f"/api/admin/users/?organization={bank_a.id}").json()
    assert {u["username"] for u in users} == {"officer_a"}


def test_admin_unknown_user_id_is_404(admin):
    assert client_for(admin).get("/api/admin/users/999999/").status_code == 404
