"""N-22 comment alerts stay tenant-scoped and transactional."""

import pytest

from domains.accounts.roles import Role
from domains.comments.models import Comment
from domains.issues.models import Issue, IssueStatus
from domains.notifications.models import Notification, OutboxMessage

from .conftest import client_for

pytestmark = pytest.mark.django_db


@pytest.fixture
def submitted_issue(bank_a, officer_a, support):
    return Issue.objects.create(
        organization=bank_a,
        created_by=officer_a,
        submitted_by=officer_a,
        status=IssueStatus.SUBMITTED,
        assignee=support,
        title="Synthetic comment notification",
        reference="SR-N22-COMMENT",
    )


def test_bank_comment_notifies_datasoft_without_cross_bank_leak(
    submitted_issue, officer_a, officer_b, support, bank_b, make_user
):
    other_bank_verifier = make_user("other_bank_verifier", bank_b, Role.ISSUE_VERIFIER)

    response = client_for(officer_a).post(
        f"/api/issues/{submitted_issue.pk}/comments/",
        {"body": "Please clarify the delivery details."},
        format="json",
    )

    assert response.status_code == 201
    assert Notification.objects.filter(
        issue=submitted_issue,
        recipient=support,
        kind="COMMENT_ADDED",
    ).exists()
    assert not Notification.objects.filter(
        recipient__in=[officer_a, officer_b, other_bank_verifier]
    ).exists()
    assert OutboxMessage.objects.filter(
        recipient=support,
        channel=OutboxMessage.Channel.EMAIL,
        status=OutboxMessage.Status.PENDING,
    ).exists()


def test_datasoft_comment_notifies_only_the_issue_bank(
    submitted_issue, officer_a, officer_b, support, bank_a, bank_b, make_user
):
    verifier = make_user("issue_bank_verifier", bank_a, Role.ISSUE_VERIFIER)
    other_bank_verifier = make_user("other_bank_verifier", bank_b, Role.ISSUE_VERIFIER)

    response = client_for(support).post(
        f"/api/issues/{submitted_issue.pk}/comments/",
        {"body": "The requested clarification is available."},
        format="json",
    )

    assert response.status_code == 201
    assert set(
        Notification.objects.filter(issue=submitted_issue).values_list("recipient_id", flat=True)
    ) == {officer_a.pk, verifier.pk}
    assert not Notification.objects.filter(
        recipient__in=[support, officer_b, other_bank_verifier]
    ).exists()


def test_comment_rolls_back_when_notification_enqueue_fails(
    submitted_issue, officer_a, monkeypatch
):
    def fail_enqueue(**_kwargs):
        raise RuntimeError("synthetic outbox failure")

    monkeypatch.setattr("domains.notifications.services.notify", fail_enqueue)

    with pytest.raises(RuntimeError, match="synthetic outbox failure"):
        client_for(officer_a).post(
            f"/api/issues/{submitted_issue.pk}/comments/",
            {"body": "This write must roll back."},
            format="json",
        )

    assert not Comment.objects.filter(issue=submitted_issue).exists()
    assert not Notification.objects.exists()
    assert not OutboxMessage.objects.exists()
