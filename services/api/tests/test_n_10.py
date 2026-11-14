import pytest

from domains.accounts.roles import Role
from domains.issues.models import Issue, IssueEvent
from domains.products.models import Product

from .conftest import client_for
from .test_n_06 import payload

pytestmark = pytest.mark.django_db


def test_submission_is_atomic_once_and_visible_to_staff(bank_a, officer_a, support, make_user):
    product = Product.objects.create(name="Synthetic Core")
    client = client_for(officer_a)
    issue = client.post("/api/issues/", payload(product.pk), format="json").json()
    path = f"/api/issues/{issue['id']}/"
    verifier = make_user("verifier_a", bank_a, Role.ISSUE_VERIFIER)
    assert client_for(verifier).post(f"{path}submit/").status_code == 403
    submitted = client.post(f"{path}submit/")
    assert submitted.status_code == 200, submitted.content
    assert submitted.json()["status"] == "SUBMITTED"
    assert submitted.json()["submitted_by"] == officer_a.pk
    assert submitted.json()["submitted_at"]
    assert client.post(f"{path}submit/").status_code == 400
    issue_db = Issue.objects.get(pk=issue["id"])
    events = list(IssueEvent.objects.filter(issue=issue_db))
    assert len(events) == 1
    assert events[0].actor_id == officer_a.pk
    assert events[0].from_status == "DRAFT" and events[0].to_status == "SUBMITTED"
    assert client_for(support).get(path).status_code == 200
    assert client.patch(path, {"title": "Too late"}, format="json").status_code == 403


def test_related_issue_must_be_same_bank(officer_a, officer_b):
    product = Product.objects.create(name="Synthetic Core")
    a = client_for(officer_a)
    b = client_for(officer_b)
    existing = b.post("/api/issues/", payload(product.pk), format="json").json()
    response = a.post(
        "/api/issues/", payload(product.pk) | {"related_request": existing["id"]}, format="json"
    )
    assert response.status_code == 400
    assert not Issue.objects.filter(organization=officer_a.account.organization).exists()
