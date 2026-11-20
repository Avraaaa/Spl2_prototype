import pytest

from domains.audit.models import AuditRecord
from domains.audit.services import anchor_head, verify_chain
from domains.comments.models import Comment
from domains.issues.models import Issue, IssueStatus

pytestmark = pytest.mark.django_db


def test_comment_is_audited_without_retaining_body(officer_a):
    issue = Issue.objects.create(
        organization=officer_a.account.organization,
        created_by=officer_a,
        status=IssueStatus.SUBMITTED,
        title="Audit comment",
    )
    Comment.objects.create(issue=issue, author=officer_a, body="Private synthetic note")

    record = AuditRecord.objects.get(action="issue.comment")
    assert record.payload == {"issue_id": issue.pk, "body_length": len("Private synthetic note")}
    assert "Private synthetic note" not in str(record.payload)


def test_external_anchor_file_is_checked_when_configured(officer_a, tmp_path, monkeypatch):
    issue = Issue.objects.create(
        organization=officer_a.account.organization,
        created_by=officer_a,
        status=IssueStatus.SUBMITTED,
        title="External anchor",
    )
    from domains.issues.models import IssueEvent

    IssueEvent.objects.create(
        issue=issue,
        actor=officer_a,
        kind="SUBMITTED",
        from_status=IssueStatus.DRAFT,
        to_status=IssueStatus.SUBMITTED,
    )
    monkeypatch.setenv("AUDIT_ANCHOR_FILE", str(tmp_path / "anchors.jsonl"))
    anchor_head(organization=issue.organization, actor=officer_a)
    assert verify_chain(issue.organization)["valid"] is True
    (tmp_path / "anchors.jsonl").unlink()
    assert verify_chain(issue.organization)["valid"] is False
