import pytest

from domains.accounts.roles import Role
from domains.products.models import Product

from .conftest import client_for

pytestmark = pytest.mark.django_db


def payload(product_id):
    return {
        "title": "Synthetic login failure",
        "description": "Test environment only",
        "request_type": "SUPPORT",
        "product": product_id,
        "priority": "MEDIUM",
    }


def test_officer_creates_and_edits_draft(bank_a, officer_a, make_user):
    product = Product.objects.create(name="Synthetic Core")
    client = client_for(officer_a)
    created = client.post("/api/issues/", payload(product.pk), format="json")
    assert created.status_code == 201, created.content
    issue = created.json()
    assert issue["status"] == "DRAFT"
    assert issue["reference"].startswith("SR-")
    edited = client.patch(
        f"/api/issues/{issue['id']}/", {"title": "Updated synthetic title"}, format="json"
    )
    assert edited.status_code == 200
    assert edited.json()["title"] == "Updated synthetic title"
    verifier = make_user("verifier_a", bank_a, Role.ISSUE_VERIFIER)
    assert (
        client_for(verifier).post("/api/issues/", payload(product.pk), format="json").status_code
        == 403
    )


def test_cross_bank_and_staff_draft_isolation(bank_a, bank_b, officer_a, officer_b, support):
    product = Product.objects.create(name="Synthetic Core")
    a = client_for(officer_a)
    b = client_for(officer_b)
    issue = a.post("/api/issues/", payload(product.pk), format="json").json()
    path = f"/api/issues/{issue['id']}/"
    for other in (b, client_for(support)):
        assert all(row["id"] != issue["id"] for row in other.get("/api/issues/").json())
        assert other.get(path).status_code == 404
        assert other.patch(path, {"title": "Intrusion"}, format="json").status_code == 404
        assert other.delete(path).status_code == 404
        assert other.post(f"{path}submit/").status_code == 404
    assert b.get("/api/issues/", {"search": issue["reference"]}).json() == []


def test_creator_only_edits_and_deletes_draft(bank_a, officer_a, make_user):
    product = Product.objects.create(name="Synthetic Core")
    other = make_user("second_officer", bank_a, Role.ISSUE_OFFICER)
    issue = client_for(officer_a).post("/api/issues/", payload(product.pk), format="json").json()
    path = f"/api/issues/{issue['id']}/"
    assert client_for(other).patch(path, {"title": "No"}, format="json").status_code == 403
    assert client_for(other).delete(path).status_code == 403
    assert client_for(officer_a).delete(path).status_code == 204
