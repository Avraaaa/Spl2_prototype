"""Append-only audit chain and privilege checks."""

import pytest

from domains.audit.models import AuditRecord
from domains.audit.services import verify_chain
from domains.issues.models import IssueEvent, IssueStatus

from .conftest import client_for

pytestmark = pytest.mark.django_db


def test_issue_events_append_and_verify_audit_chain(officer_a, admin):
    issue = officer_a.created_issues.create(
        organization=officer_a.account.organization,
        status=IssueStatus.SUBMITTED,
        title="Audit chain test",
        reference="SR-9914",
    )
    IssueEvent.objects.create(
        issue=issue,
        actor=officer_a,
        kind="SUBMITTED",
        from_status=IssueStatus.DRAFT,
        to_status=IssueStatus.SUBMITTED,
    )

    record = AuditRecord.objects.get(organization=issue.organization)
    assert record.sequence == 1
    assert verify_chain(issue.organization)["valid"] is True
    assert client_for(admin).get("/api/audit/verify/").json()["valid"] is True

    AuditRecord.objects.filter(pk=record.pk).update(payload={"tampered": True})
    assert verify_chain(issue.organization) == {"valid": False, "first_invalid_sequence": 1}


def test_bank_user_cannot_verify_audit(officer_a):
    assert client_for(officer_a).get("/api/audit/verify/").status_code == 403
