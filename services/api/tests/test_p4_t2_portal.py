"""P4-T2: display names, bank filter and queue filters on the issue API (two banks)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from domains.issues.models import Issue, IssueStatus

from .conftest import client_for

pytestmark = pytest.mark.django_db


def make_issue(officer, *, status=IssueStatus.SUBMITTED, title="Synthetic issue", **fields):
    return Issue.objects.create(
        organization=officer.account.organization,
        created_by=officer,
        status=status,
        title=title,
        description="Synthetic detail",
        **fields,
    )


def test_issue_exposes_display_names(officer_a, support):
    issue = make_issue(officer_a, status=IssueStatus.ACCEPTED, assignee=support)
    data = client_for(officer_a).get(f"/api/issues/{issue.pk}/").json()
    assert data["organization_name"] == "Northwind Demo Bank"
    assert data["organization_code"] == "NWD"
    assert data["created_by_name"] == officer_a.account.full_name
    assert data["assignee_name"] == support.account.full_name


def test_unassigned_issue_has_no_assignee_name(officer_a):
    issue = make_issue(officer_a)
    data = client_for(officer_a).get(f"/api/issues/{issue.pk}/").json()
    assert data["assignee_name"] is None


def test_related_and_recurring_references(officer_a):
    old = make_issue(officer_a, status=IssueStatus.CLOSED, title="Old problem")
    old.reference = "SR-9001"
    old.save()
    new = make_issue(officer_a, title="Again", recurring_of=old, related_request=old)
    data = client_for(officer_a).get(f"/api/issues/{new.pk}/").json()
    assert data["recurring_of_reference"] == "SR-9001"
    assert data["recurring_of_title"] == "Old problem"
    assert data["related_request_reference"] == "SR-9001"
    assert data["related_request_title"] == "Old problem"


def test_names_do_not_leak_across_banks(officer_a, officer_b):
    make_issue(officer_b, title="Bank B secret")
    rows = client_for(officer_a).get("/api/issues/").json()
    assert rows == []
    text = client_for(officer_a).get("/api/issues/").content.decode()
    assert "Riverstone" not in text


def test_staff_can_filter_by_bank_and_banks_see_only_own(officer_a, officer_b, admin, bank_b):
    own = make_issue(officer_a, title="A one")
    other = make_issue(officer_b, title="B one")
    staff = client_for(admin)
    assert {r["id"] for r in staff.get("/api/issues/").json()} == {own.pk, other.pk}
    only_b = staff.get("/api/issues/", {"organization": str(bank_b.pk)}).json()
    assert [r["id"] for r in only_b] == [other.pk]
    # A bank user cannot widen scope with the filter.
    spoof = client_for(officer_a).get("/api/issues/", {"organization": str(bank_b.pk)}).json()
    assert spoof == []


def test_invalid_organization_filter_is_rejected(admin):
    response = client_for(admin).get("/api/issues/", {"organization": "abc"})
    assert response.status_code == 400


def test_assignee_me_and_oldest_first_and_overdue(officer_a, admin, support):
    now = timezone.now()
    first = make_issue(officer_a, title="First", submitted_at=now - timedelta(days=3))
    second = make_issue(officer_a, title="Second", submitted_at=now - timedelta(days=1))
    mine = make_issue(
        officer_a,
        status=IssueStatus.IN_PROGRESS,
        assignee=support,
        tentative_delivery_date=timezone.localdate() - timedelta(days=2),
    )
    staff = client_for(support)
    queue = staff.get("/api/issues/", {"status": "SUBMITTED", "ordering": "oldest"}).json()
    assert [r["id"] for r in queue] == [first.pk, second.pk]
    assigned = staff.get("/api/issues/", {"assignee": "me"}).json()
    assert [r["id"] for r in assigned] == [mine.pk]
    overdue = staff.get("/api/issues/", {"overdue": "true"}).json()
    assert [r["id"] for r in overdue] == [mine.pk]
    assert client_for(admin).get("/api/issues/", {"ordering": "bogus"}).status_code == 400


def test_dashboard_counts_per_bank_for_staff_only(officer_a, officer_b, admin):
    make_issue(officer_a)
    make_issue(officer_a)
    make_issue(officer_b)
    staff = client_for(admin).get("/api/reports/dashboard/").json()
    assert staff["by_bank"] == {"Northwind Demo Bank": 2, "Riverstone Demo Bank": 1}
    assert staff["overdue"] == 0
    bank = client_for(officer_a).get("/api/reports/dashboard/").json()
    assert "by_bank" not in bank
