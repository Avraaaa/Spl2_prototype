"""Original content reads are permissioned, scoped, and audited."""

import pytest

from domains.audit.models import AuditRecord
from domains.issues.models import Issue, IssueStatus

from .conftest import client_for

pytestmark = pytest.mark.django_db


def test_admin_original_read_appends_audit_and_other_roles_are_denied(admin, support, officer_a):
    issue = Issue.objects.create(
        organization=officer_a.account.organization,
        created_by=officer_a,
        status=IssueStatus.SUBMITTED,
        reference="SR-99001",
        title="Masked title",
        description="Masked detail",
    )
    before = AuditRecord.objects.count()
    response = client_for(admin).get(f"/api/issues/{issue.pk}/original/")
    assert response.status_code == 200
    assert response.json()["description"] == "Masked detail"
    record = AuditRecord.objects.latest("sequence")
    assert AuditRecord.objects.count() == before + 1
    assert record.actor == admin
    assert record.action == "ISSUE_ORIGINAL_VIEWED"
    assert record.payload["issue_id"] == issue.pk
    assert record.payload["request_method"] == "GET"
    assert record.payload["request_path"] == f"/api/issues/{issue.pk}/original/"
    assert client_for(support).get(f"/api/issues/{issue.pk}/original/").status_code == 403


def test_original_read_is_hidden_across_tenants(admin, officer_a, officer_b):
    issue = Issue.objects.create(
        organization=officer_a.account.organization,
        created_by=officer_a,
        status=IssueStatus.SUBMITTED,
        reference="SR-99002",
    )
    assert client_for(officer_b).get(f"/api/issues/{issue.pk}/original/").status_code == 404
