"""P4-T1 reporting, recurrence, and deadline boundaries with synthetic banks."""

import csv
import io
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from domains.issues.models import Issue, IssueEvent, IssueStatus

from .conftest import client_for

pytestmark = pytest.mark.django_db


def issue_for(officer, *, status=IssueStatus.SUBMITTED, title="Synthetic issue", **fields):
    description = fields.pop("description", "Synthetic detail")
    return Issue.objects.create(
        organization=officer.account.organization,
        created_by=officer,
        status=status,
        title=title,
        description=description,
        **fields,
    )


def test_reports_and_exports_are_tenant_scoped(officer_a, officer_b, admin, bank_b):
    own = issue_for(officer_a, title="Own issue")
    foreign = issue_for(officer_b, title="Foreign issue")
    client = client_for(officer_a)
    query = {"bank": str(bank_b.pk)}
    detailed = client.get("/api/reports/detailed/", query)
    summary = client.get("/api/reports/summary/", query)
    assert detailed.status_code == summary.status_code == 200
    assert [row["id"] for row in detailed.json()] == [own.pk]
    assert summary.json()["total"] == 1
    assert "by_bank" not in summary.json()
    for name in ("detailed", "summary"):
        export = client.get(f"/api/reports/{name}/csv/", query)
        assert export.status_code == 200
        assert export["Content-Type"].startswith("text/csv")
        assert "attachment" in export["Content-Disposition"]
        assert "Foreign issue" not in export.content.decode("utf-8-sig")
    assert client_for(admin).get("/api/reports/summary/").json()["total"] == 2
    assert foreign.pk != own.pk


def test_default_year_filters_old_rows_and_summary_math(officer_a, officer_b, admin):
    now = timezone.localtime()
    old = issue_for(officer_a, title="Previous year")
    Issue.objects.filter(pk=old.pk).update(created_at=now.replace(year=now.year - 1))
    current = issue_for(officer_a, status=IssueStatus.CLOSED, closed_at=now)
    issue_for(officer_b, status=IssueStatus.PENDING)
    response = client_for(officer_a).get("/api/reports/summary/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["by_status"]["CLOSED"] == 1
    assert sum(data["by_month"].values()) == 1
    assert client_for(admin).get("/api/reports/summary/").json()["total"] == 2
    detail = client_for(officer_a).get("/api/reports/detailed/").json()
    assert current.pk in [r["id"] for r in detail]


def test_csv_headers_and_formula_cells(officer_a):
    issue_for(officer_a, title="=HYPERLINK(1)", description="+unsafe detail")
    response = client_for(officer_a).get("/api/reports/detailed/csv/")
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert rows[0] == [
        "reference_id",
        "bank",
        "issue_officer",
        "title",
        "issue_detail",
        "status",
        "creation_date",
        "submission_date",
        "tentative_delivery_date",
        "actual_delivery_date",
        "last_status_update_date",
        "closure_date",
    ]
    assert rows[1][3] == "'=HYPERLINK(1)"
    assert rows[1][4] == "'+unsafe detail"
    assert client_for(officer_a).get("/api/reports/summary/csv/").status_code == 200


def test_overdue_flag_filter_and_delivery(officer_a):
    late = issue_for(
        officer_a,
        tentative_delivery_date=timezone.localdate() - timedelta(days=1),
    )
    delivered = issue_for(
        officer_a,
        tentative_delivery_date=timezone.localdate() - timedelta(days=1),
        actual_delivery_at=timezone.now(),
    )
    client = client_for(officer_a)
    assert client.get(f"/api/issues/{late.pk}/").json()["is_overdue"] is True
    assert client.get(f"/api/issues/{delivered.pk}/").json()["is_overdue"] is False
    assert {r["id"] for r in client.get("/api/issues/").json() if r["is_overdue"]} == {late.pk}
    overdue = client.get("/api/reports/detailed/", {"overdue": "true"}).json()
    assert [r["id"] for r in overdue] == [late.pk]


def test_recurring_link_requires_closed_same_bank(officer_a, officer_b):
    closed = issue_for(
        officer_a,
        status=IssueStatus.CLOSED,
        closed_at=timezone.now() - timedelta(days=31),
    )
    other_bank = issue_for(officer_b, status=IssueStatus.CLOSED)
    open_issue = issue_for(officer_a)
    client = client_for(officer_a)
    for invalid in (other_bank.pk, open_issue.pk):
        response = client.post("/api/issues/", {"recurring_of": invalid}, format="json")
        assert response.status_code == 400
    response = client.post("/api/issues/", {"recurring_of": closed.pk}, format="json")
    assert response.status_code == 201
    child = response.json()
    assert child["recurring_of"] == closed.pk
    assert child["id"] in client.get(f"/api/issues/{closed.pk}/").json()["recurring_requests"]
    assert client.get(f"/api/issues/{other_bank.pk}/").status_code == 404


def test_reverse_recurring_link_never_reveals_foreign_or_other_officer_drafts(
    officer_a, officer_b, bank_a, make_user
):
    from domains.accounts.roles import Role

    previous = issue_for(officer_a, status=IssueStatus.CLOSED)
    foreign = issue_for(officer_b, recurring_of=previous)
    other_officer = make_user("second_a", bank_a, Role.ISSUE_OFFICER)
    hidden_draft = issue_for(other_officer, status=IssueStatus.DRAFT, recurring_of=previous)
    visible = client_for(officer_a).get(f"/api/issues/{previous.pk}/").json()
    assert foreign.pk not in visible["recurring_requests"]
    assert hidden_draft.pk not in visible["recurring_requests"]


def test_dashboard_counts_do_not_cross_banks(officer_a, officer_b, admin):
    issue_for(officer_a, status=IssueStatus.SUBMITTED)
    issue_for(officer_b, status=IssueStatus.CLOSED, actual_delivery_at=timezone.now())
    bank_data = client_for(officer_a).get("/api/reports/dashboard/").json()
    assert bank_data["total"] == 1
    assert "pending_intake" not in bank_data
    staff_data = client_for(admin).get("/api/reports/dashboard/").json()
    assert staff_data["total"] == 2
    assert staff_data["pending_intake"] == 1
    assert staff_data["recent_deliveries"] == 1
    assert client_for(officer_a).get("/api/reports/banks/").status_code == 403
    assert len(client_for(admin).get("/api/reports/banks/").json()) == 2


def test_dashboard_drafts_are_visible_only_to_their_creator(officer_a, bank_a, make_user):
    from domains.accounts.roles import Role

    other_officer = make_user("private_draft_author", bank_a, Role.ISSUE_OFFICER)
    issue_for(other_officer, status=IssueStatus.DRAFT)
    assert client_for(officer_a).get("/api/reports/dashboard/").json()["total"] == 0
    assert client_for(other_officer).get("/api/reports/dashboard/").json()["total"] == 1


def test_summary_counts_reopened_and_recurring_without_other_bank(officer_a, officer_b, admin):
    previous = issue_for(officer_a, status=IssueStatus.CLOSED)
    recurring = issue_for(officer_a, recurring_of=previous)
    IssueEvent.objects.create(
        issue=previous,
        actor=officer_a,
        kind="REOPENED",
        from_status=IssueStatus.CLOSED,
        to_status=IssueStatus.IN_PROGRESS,
    )
    issue_for(officer_b, status=IssueStatus.CLOSED)
    own = client_for(officer_a).get("/api/reports/summary/").json()
    assert own["total"] == 2
    assert own["reopened_count"] == 1
    assert own["recurring_count"] == 1
    assert sum(own["by_status"].values()) == 2
    assert sum(own["by_month"].values()) == 2
    all_banks = client_for(admin).get("/api/reports/summary/").json()
    assert all_banks["total"] == sum(all_banks["by_bank"].values()) == 3
    detailed = client_for(officer_a).get("/api/reports/detailed/").json()
    assert recurring.pk in [r["id"] for r in detailed]


def test_report_filters_and_authentication(officer_a, officer_b, admin, bank_a):
    issue_for(officer_a, status=IssueStatus.SUBMITTED)
    issue_for(officer_b, status=IssueStatus.CLOSED)
    staff = client_for(admin)
    assert staff.get("/api/reports/summary/", {"bank": bank_a.pk}).json()["total"] == 1
    assert staff.get("/api/reports/summary/", {"status": "CLOSED"}).json()["total"] == 1
    prior_year = staff.get(
        "/api/reports/summary/", {"start": "2000-01-01", "end": "2000-12-31"}
    ).json()
    assert prior_year["total"] == 0
    assert staff.get("/api/reports/detailed/", {"start": "bad"}).status_code == 400
    for path in ("detailed/", "summary/", "detailed/csv/", "summary/csv/", "dashboard/"):
        assert client_for().get(f"/api/reports/{path}").status_code in (401, 403)


def test_synthetic_seed_populates_overdue_closed_recurring_and_months(settings):
    settings.DEBUG = True
    call_command("seed_demo")
    call_command("seed_demo")
    for bank_code in ("NWD", "RSD"):
        issues = Issue.objects.filter(organization__code=bank_code)
        assert issues.filter(status=IssueStatus.CLOSED).count() == 1
        assert issues.filter(recurring_of__isnull=False).count() == 1
        assert (
            issues.filter(
                tentative_delivery_date__lt=timezone.localdate(),
                actual_delivery_at__isnull=True,
            ).count()
            == 1
        )
        assert issues.dates("created_at", "month").count() >= 2
