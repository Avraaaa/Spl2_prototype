import pytest

from domains.search.models import IssueLabelSelection, Label, SuggestionFeedback

from .conftest import client_for
from .test_p5_t1_search import make_issue

pytestmark = pytest.mark.django_db


def test_accepting_label_persists_human_selection(officer_a):
    issue = make_issue(officer_a, "Login", "Authentication timeout")
    label = Label.objects.create(
        name="Authentication", description="Login and authentication failures"
    )

    response = client_for(officer_a).post(
        "/api/search/feedback/",
        {"kind": "label", "accepted": True, "issue": issue.pk, "label": label.pk},
        format="json",
    )

    assert response.status_code == 201, response.content
    selection = IssueLabelSelection.objects.get(issue=issue)
    assert selection.label_id == label.pk
    assert SuggestionFeedback.objects.filter(issue=issue, label=label, accepted=True).exists()


def test_removing_label_deletes_human_selection(officer_a):
    issue = make_issue(officer_a, "Login", "Authentication timeout")
    label = Label.objects.create(name="Authentication", keywords=["login"])
    client = client_for(officer_a)
    client.post(
        "/api/search/feedback/",
        {"kind": "label", "accepted": True, "issue": issue.pk, "label": label.pk},
        format="json",
    )

    response = client.post(
        "/api/search/feedback/",
        {"kind": "label", "accepted": False, "issue": issue.pk},
        format="json",
    )

    assert response.status_code == 201
    assert not IssueLabelSelection.objects.filter(issue=issue).exists()
