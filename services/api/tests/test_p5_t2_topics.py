"""Recent topic proposals and held-out ranking metrics."""

import pytest

from domains.issues.models import Issue, IssueStatus
from domains.search.models import TopicProposal
from domains.search.services import precision_at_k, recall_at_k

from .conftest import client_for

pytestmark = pytest.mark.django_db


def make_issue(user, title):
    return Issue.objects.create(
        organization=user.account.organization,
        created_by=user,
        submitted_by=user,
        status=IssueStatus.SUBMITTED,
        title=title,
        description=title,
    )


def test_topic_proposals_are_admin_only_and_bank_scoped(officer_a, admin):
    make_issue(officer_a, "Login failure")
    make_issue(officer_a, "Login timeout")
    response = client_for(admin).post("/api/search/topics/", {}, format="json")

    assert response.status_code == 201
    assert TopicProposal.objects.filter(organization=officer_a.account.organization).exists()
    assert client_for(officer_a).get("/api/search/topics/").status_code == 403


def test_topic_metrics_are_bounded():
    assert precision_at_k({1, 2}, [1, 3, 2], 3) == pytest.approx(2 / 3)
    assert recall_at_k({1, 2}, [1, 3, 2], 3) == 1.0
    assert recall_at_k(set(), [1], 5) == 0.0
