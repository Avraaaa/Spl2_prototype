"""P1-T2: two-bank isolation for the account APIs and reusable tenant selectors."""

import pytest
from django.contrib.auth.models import AnonymousUser
from django.http import Http404

from domains.accounts.models import Account, Membership
from domains.accounts.roles import Role
from domains.tenants.models import Organization
from domains.tenants.selectors import authorized_rows, get_authorized_object_or_404

from .conftest import client_for, login

pytestmark = pytest.mark.django_db


def test_bank_selector_excludes_other_bank_and_datasoft(officer_a, officer_b, admin):
    rows = Account.objects.all()
    visible = authorized_rows(officer_a, rows)
    assert list(visible.values_list("user_id", flat=True)) == [officer_a.id]
    assert not visible.filter(user=officer_b).exists()
    assert not visible.filter(user=admin).exists()

    with pytest.raises(Http404):
        get_authorized_object_or_404(officer_a, rows, officer_b.account.pk)
    assert get_authorized_object_or_404(officer_a, rows, officer_a.account.pk) == officer_a.account


def test_staff_cross_bank_access_requires_explicit_policy(admin, support, officer_a, officer_b):
    rows = Account.objects.all()
    assert not authorized_rows(admin, rows).exists()
    assert not authorized_rows(support, rows).exists()
    with pytest.raises(Http404):
        get_authorized_object_or_404(admin, rows, officer_b.account.pk)
    assert (
        get_authorized_object_or_404(admin, rows, officer_b.account.pk, allow_datasoft=True)
        == officer_b.account
    )
    assert set(
        authorized_rows(admin, rows, allow_datasoft=True).values_list("user_id", flat=True)
    ) == {admin.id, support.id, officer_a.id, officer_b.id}
    assert set(
        authorized_rows(support, rows, allow_datasoft=True).values_list("user_id", flat=True)
    ) == {admin.id, support.id, officer_a.id, officer_b.id}
    assert (
        not authorized_rows(admin, rows.filter(user=officer_a), allow_datasoft=True)
        .filter(user=officer_b)
        .exists()
    )


def test_selector_fails_closed_without_matching_active_membership(
    officer_a, officer_b, bank_a, bank_b
):
    rows = Account.objects.all()
    assert not authorized_rows(AnonymousUser(), rows).exists()
    Membership.objects.filter(user=officer_a).delete()
    Membership.objects.create(user=officer_a, organization=bank_b, role=Role.ISSUE_OFFICER)
    assert not authorized_rows(officer_a, rows).exists()
    assert client_for(officer_a).get("/api/auth/me/").status_code == 403
    assert login("officer_a")[1].status_code == 401

    Membership.objects.filter(user=officer_a).delete()
    Membership.objects.create(user=officer_a, organization=bank_a, role=Role.ISSUE_OFFICER)
    bank_a.is_active = False
    bank_a.save(update_fields=["is_active"])
    assert not authorized_rows(officer_a, rows).exists()
    assert client_for(officer_a).get("/api/auth/me/").status_code == 403
    assert login("officer_a")[1].status_code == 401
    assert not authorized_rows(officer_b, rows).filter(user=officer_a).exists()


def test_staff_role_cannot_be_borrowed_from_another_organization(officer_a, admin, datasoft):
    Membership.objects.create(user=officer_a, organization=datasoft, role=Role.DATASOFT_ADMIN)
    client = client_for(officer_a)
    assert client.get("/api/admin/users/").status_code == 403
    assert client.get("/api/admin/organizations/").status_code == 403
    assert (
        not authorized_rows(officer_a, Account.objects.all(), allow_datasoft=True)
        .filter(user=admin)
        .exists()
    )
    assert client.get("/api/auth/me/").json()["roles"] == ["ISSUE_OFFICER"]


@pytest.mark.parametrize("who", ["officer_a", "officer_b", "support"])
def test_unprivileged_users_cannot_guess_or_spoof_admin_resources(
    request, who, officer_a, officer_b, bank_a, bank_b
):
    client = client_for(request.getfixturevalue(who))
    other = officer_b if who == "officer_a" else officer_a
    foreign_bank = bank_b if who == "officer_a" else bank_a
    headers = {"HTTP_X_ORGANIZATION_ID": str(foreign_bank.id)}
    assert client.get(f"/api/admin/users/{other.id}/", **headers).status_code == 403
    assert (
        client.get(f"/api/admin/users/?organization={foreign_bank.id}", **headers).status_code
        == 403
    )
    assert client.get(f"/api/admin/organizations/{foreign_bank.id}/", **headers).status_code in (
        403,
        404,
        405,
    )
    assert (
        client.put(
            f"/api/admin/users/{other.id}/roles/",
            {"roles": ["ISSUE_VERIFIER"], "organization": foreign_bank.id},
            format="json",
            **headers,
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/admin/users/{other.id}/deactivate/",
            {"organization": foreign_bank.id},
            format="json",
            **headers,
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/admin/users/{other.id}/reset-password/",
            {"organization": foreign_bank.id},
            format="json",
            **headers,
        ).status_code
        == 403
    )


def test_organization_rows_use_same_object_policy(officer_a, bank_a, bank_b):
    rows = Organization.objects.all()
    visible = authorized_rows(officer_a, rows, organization_field="pk")
    assert list(visible) == [bank_a]
    with pytest.raises(Http404):
        get_authorized_object_or_404(officer_a, rows, bank_b.pk, organization_field="pk")
