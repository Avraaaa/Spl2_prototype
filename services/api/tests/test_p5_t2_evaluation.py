import pytest

from domains.search.models import IssueLabelSelection, Label

from .conftest import client_for
from .test_p5_t2_topics import make_issue

pytestmark = pytest.mark.django_db


def test_topic_discovery_excludes_confirmed_label_examples(officer_a, admin):
    labeled = make_issue(officer_a, "Authentication timeout")
    unlabeled = make_issue(officer_a, "Authentication timeout again")
    make_issue(officer_a, "Authentication timeout later")
    label = Label.objects.create(name="Authentication", keywords=["authentication"])
    IssueLabelSelection.objects.create(issue=labeled, label=label, actor=officer_a)

    response = client_for(admin).post("/api/search/topics/", {}, format="json")

    assert response.status_code == 201
    proposals = client_for(admin).get("/api/search/topics/").json()
    assert all(labeled.pk not in item.get("issue_ids", []) for item in proposals)
    assert any(unlabeled.pk in item.get("issue_ids", []) for item in proposals)


def test_admin_can_read_feedback_evaluation_but_bank_cannot(officer_a, admin):
    issue = make_issue(officer_a, "Login")
    response = client_for(officer_a).post(
        "/api/search/feedback/",
        {"kind": "duplicate", "accepted": True, "issue": issue.pk},
        format="json",
    )
    assert response.status_code == 201

    report = client_for(admin).get("/api/search/evaluation/")
    assert report.status_code == 200
    assert report.json()["duplicate_feedback"]["accepted"] == 1
    assert client_for(officer_a).get("/api/search/evaluation/").status_code == 403
