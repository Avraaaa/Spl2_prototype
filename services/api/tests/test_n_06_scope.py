import pytest

from domains.accounts.roles import Role
from domains.issues.models import Issue, IssueEvent
from domains.products.models import Product

from .conftest import client_for
from .test_n_06 import payload

pytestmark = pytest.mark.django_db


def test_draft_visible_only_to_creator_and_submitted_visible_to_bank_and_staff(
    bank_a, officer_a, officer_b, support, make_user
):
    product = Product.objects.create(name="Synthetic Core")
    other_officer = make_user("scope_officer", bank_a, Role.ISSUE_OFFICER)
    creator = client_for(officer_a)
    draft = creator.post("/api/issues/", payload(product.pk), format="json").json()
    path = f"/api/issues/{draft['id']}/"
    for user in (other_officer, support, officer_b):
        client = client_for(user)
        assert client.get(path).status_code == 404
        assert draft["id"] not in [row["id"] for row in client.get("/api/issues/").json()]
    assert creator.post(f"{path}submit/").status_code == 200
    assert client_for(other_officer).get(path).status_code == 200
    assert client_for(support).get(path).status_code == 200
    assert client_for(officer_b).get(path).status_code == 404


def test_invalid_submission_keeps_draft_and_no_event(officer_a):
    client = client_for(officer_a)
    issue = client.post("/api/issues/", {"title": "Incomplete"}, format="json").json()
    assert client.post(f"/api/issues/{issue['id']}/submit/").status_code == 400
    assert Issue.objects.get(pk=issue["id"]).status == "DRAFT"
    assert IssueEvent.objects.filter(issue_id=issue["id"]).count() == 0


def test_issue_list_filters_and_search_are_tenant_scoped(officer_a, officer_b):
    product = Product.objects.create(name="Synthetic Core")
    a = client_for(officer_a)
    b = client_for(officer_b)
    own = a.post("/api/issues/", payload(product.pk), format="json").json()
    foreign = b.post("/api/issues/", payload(product.pk), format="json").json()
    assert [row["id"] for row in a.get("/api/issues/", {"search": own["reference"]}).json()] == [
        own["id"]
    ]
    assert a.get("/api/issues/", {"search": foreign["reference"]}).json() == []
    assert a.get("/api/issues/", {"status": "SUBMITTED"}).json() == []


def test_body_cannot_choose_another_bank(officer_a, bank_b):
    product = Product.objects.create(name="Synthetic Core")
    client = client_for(officer_a)
    response = client.post(
        "/api/issues/", payload(product.pk) | {"organization": bank_b.pk}, format="json"
    )
    assert response.status_code == 400
    assert Issue.objects.count() == 0
