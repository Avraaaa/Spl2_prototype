import pytest

from domains.issues.models import Issue, IssueEvent
from domains.products.models import Product

from .conftest import client_for
from .test_n_06 import payload

pytestmark = pytest.mark.django_db


def test_whitespace_only_required_text_does_not_submit(officer_a):
    product = Product.objects.create(name="Synthetic Core")
    client = client_for(officer_a)
    draft = client.post(
        "/api/issues/",
        payload(product.pk) | {"title": "   ", "description": "\n  "},
        format="json",
    ).json()

    response = client.post(f"/api/issues/{draft['id']}/submit/")

    assert response.status_code == 400
    assert set(response.json()) == {"title", "description"}
    assert Issue.objects.get(pk=draft["id"]).status == "DRAFT"
    assert not IssueEvent.objects.filter(issue_id=draft["id"]).exists()


def test_related_request_accepts_only_submitted_same_bank_ticket(officer_a, officer_b):
    product = Product.objects.create(name="Synthetic Core")
    own = client_for(officer_a)
    foreign = client_for(officer_b)
    own_prior = own.post("/api/issues/", payload(product.pk), format="json").json()
    foreign_prior = foreign.post("/api/issues/", payload(product.pk), format="json").json()
    assert own.post(f"/api/issues/{own_prior['id']}/submit/").status_code == 200
    assert foreign.post(f"/api/issues/{foreign_prior['id']}/submit/").status_code == 200

    linked = own.post(
        "/api/issues/", payload(product.pk) | {"related_request": own_prior["id"]}, format="json"
    )
    assert linked.status_code == 201
    assert linked.json()["related_request"] == own_prior["id"]
    rejected = own.post(
        "/api/issues/",
        payload(product.pk) | {"related_request": foreign_prior["id"]},
        format="json",
    )
    assert rejected.status_code == 400
    assert rejected.json()["related_request"] == ["Invalid related request."]
