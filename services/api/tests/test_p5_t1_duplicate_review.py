import pytest

from domains.issues.models import Issue, IssueStatus
from domains.search.models import DuplicateReview

from .conftest import client_for
from .test_p5_t2_topics import make_issue

pytestmark = pytest.mark.django_db


def test_staff_can_review_same_bank_candidate_and_mark_recurring(officer_a, admin):
    issue = make_issue(officer_a, "Repeated transfer failure")
    candidate = Issue.objects.create(
        organization=officer_a.account.organization,
        created_by=officer_a,
        submitted_by=officer_a,
        status=IssueStatus.CLOSED,
        title="Earlier transfer failure",
        description="Same transfer failure",
    )
    response = client_for(admin).post(
        "/api/search/duplicate-reviews/",
        {"issue": issue.pk, "candidate_issue": candidate.pk, "decision": "recurring"},
        format="json",
    )

    assert response.status_code == 201, response.content
    issue.refresh_from_db()
    assert issue.recurring_of_id == candidate.pk
    assert DuplicateReview.objects.get(pk=response.json()["id"]).decision == "recurring"


def test_bank_cannot_review_foreign_candidate(officer_a, officer_b, admin):
    issue = make_issue(officer_a, "Own issue")
    foreign = make_issue(officer_b, "Foreign issue")
    response = client_for(admin).post(
        "/api/search/duplicate-reviews/",
        {"issue": issue.pk, "candidate_issue": foreign.pk, "decision": "confirmed"},
        format="json",
    )
    assert response.status_code == 400
