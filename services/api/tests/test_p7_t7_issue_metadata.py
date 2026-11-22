"""Acceptance criteria and confirmed labels on tenant-scoped issue APIs."""

import pytest
from django.contrib.auth.models import Permission

from domains.issues.models import Issue, IssueStatus
from domains.products.models import Product
from domains.search.models import IssueLabelSelection, Label

from .conftest import client_for

pytestmark = pytest.mark.django_db


def test_me_exposes_the_specific_original_text_capability(admin, support, officer_a):
    original_permission = Permission.objects.get(
        content_type__app_label="issues", codename="view_unmasked_original"
    )
    officer_a.user_permissions.add(original_permission)

    assert client_for(admin).get("/api/auth/me/").json()["can_view_unmasked_original"] is True
    assert client_for(officer_a).get("/api/auth/me/").json()["can_view_unmasked_original"] is True
    assert client_for(support).get("/api/auth/me/").json()["can_view_unmasked_original"] is False


def test_acceptance_criteria_is_masked_and_round_trips(officer_a):
    product = Product.objects.create(name="Synthetic Core")
    response = client_for(officer_a).post(
        "/api/issues/",
        {
            "title": "Acceptance criteria masking",
            "description": "Check masked details",
            "acceptance_criteria": "Account 123456789012 must remain private",
            "product": product.pk,
        },
        format="json",
    )

    assert response.status_code == 201, response.content
    assert response.json()["acceptance_criteria"] == "[ACCOUNT_NUMBER] must remain private"
    issue_id = response.json()["id"]
    changed = client_for(officer_a).patch(
        f"/api/issues/{issue_id}/",
        {"acceptance_criteria": "PIN 123456 should be checked"},
        format="json",
    )
    assert changed.status_code == 200, changed.content
    assert changed.json()["acceptance_criteria"] == "PIN [OTP REDACTED] should be checked"
    label = Label.objects.create(name="Read-only label")
    readonly = client_for(officer_a).patch(
        f"/api/issues/{issue_id}/", {"confirmed_label": label.pk}, format="json"
    )
    assert readonly.status_code == 400


def test_confirmed_labels_are_read_only_and_filterable_without_cross_bank_leaks(
    officer_a, officer_b, admin
):
    label = Label.objects.create(name="Authentication")
    other_label = Label.objects.create(name="Payments")
    issue_a = Issue.objects.create(
        organization=officer_a.account.organization,
        created_by=officer_a,
        status=IssueStatus.SUBMITTED,
        reference="SR-T7-A",
        title="Login issue",
    )
    issue_b = Issue.objects.create(
        organization=officer_b.account.organization,
        created_by=officer_b,
        status=IssueStatus.SUBMITTED,
        reference="SR-T7-B",
        title="Payment issue",
    )
    IssueLabelSelection.objects.create(issue=issue_a, label=label, actor=officer_a)
    IssueLabelSelection.objects.create(issue=issue_b, label=other_label, actor=officer_b)

    detail = client_for(officer_a).get(f"/api/issues/{issue_a.pk}/")
    assert detail.status_code == 200
    assert detail.json()["confirmed_label"] == {"id": label.pk, "name": label.name}

    filtered = client_for(admin).get(f"/api/issues/?label={label.pk}")
    assert filtered.status_code == 200
    assert [row["id"] for row in filtered.json()] == [issue_a.pk]
    bank_rows = client_for(officer_a).get("/api/issues/").json()
    assert {row["id"] for row in bank_rows} == {issue_a.pk}
