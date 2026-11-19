"""Tenant isolation and offline fallback checks for suggestions."""

import pytest

from domains.issues.models import Issue, IssueStatus
from domains.search.models import Label, SuggestionFeedback

from .conftest import client_for

pytestmark = pytest.mark.django_db


def make_issue(user, title, description):
    return Issue.objects.create(
        organization=user.account.organization,
        created_by=user,
        submitted_by=user,
        status=IssueStatus.SUBMITTED,
        title=title,
        description=description,
    )


def test_suggestions_are_masked_ranked_and_tenant_scoped(officer_a, officer_b):
    own = make_issue(officer_a, "Login timeout", "Authentication timeout on sign in")
    foreign = make_issue(officer_b, "Login timeout", "Authentication timeout on sign in")
    Label.objects.create(
        name="Authentication", keywords=["authentication", "login"], confidence_threshold=0.1
    )

    response = client_for(officer_a).post(
        "/api/search/suggestions/",
        {"title": "Login timeout", "description": "OTP: 123456 authentication timeout"},
        format="json",
    )

    assert response.status_code == 200
    data = response.json()
    assert [row["id"] for row in data["duplicates"]] == [own.pk]
    assert foreign.pk not in [row["id"] for row in data["duplicates"]]
    assert data["labels"][0]["name"] == "Authentication"
    assert "123456" not in str(data)


def test_feedback_cannot_reference_another_bank(officer_a, officer_b):
    foreign = make_issue(officer_b, "Foreign", "Foreign issue")
    response = client_for(officer_a).post(
        "/api/search/feedback/",
        {"kind": "duplicate", "accepted": True, "candidate_issue": foreign.pk},
        format="json",
    )

    assert response.status_code == 404
    assert not SuggestionFeedback.objects.exists()


def test_only_datasoft_admin_can_refine_labels(officer_a, admin):
    forbidden = client_for(officer_a).post(
        "/api/search/labels/",
        {"name": "Authentication", "keywords": ["login"]},
        format="json",
    )
    assert forbidden.status_code == 403

    created = client_for(admin).post(
        "/api/search/labels/",
        {"name": "Authentication", "keywords": ["login"], "confidence_threshold": 0.4},
        format="json",
    )
    assert created.status_code == 201
    edited = client_for(admin).patch(
        f"/api/search/labels/{created.data['id']}/",
        {"keywords": ["login", "signin"], "is_active": True},
        format="json",
    )
    assert edited.status_code == 200
    assert edited.data["keywords"] == ["login", "signin"]
