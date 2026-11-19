"""Regression tests for safe report exports and profile-less creators."""

import csv
import io

import pytest

from domains.issues.models import Issue, IssueStatus

from .conftest import client_for

pytestmark = pytest.mark.django_db


def test_csv_escapes_tab_and_carriage_return_formula_prefixes(officer_a):
    Issue.objects.create(
        organization=officer_a.account.organization,
        created_by=officer_a,
        status=IssueStatus.SUBMITTED,
        title="\t=CMD()",
        description="\r-HARMFUL()",
        reference="SR-9912",
    )
    response = client_for(officer_a).get("/api/reports/detailed/csv/")
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert rows[0][3] == "title"
    values = rows[1]
    assert values[3] == "'\t=CMD()"
    assert values[4] == "'\r-HARMFUL()"


def test_detailed_report_handles_creator_without_profile(officer_a, admin):
    issue = Issue.objects.create(
        organization=officer_a.account.organization,
        created_by=officer_a,
        status=IssueStatus.SUBMITTED,
        title="Profile-less creator",
        reference="SR-9913",
    )
    officer_a.account.delete()

    response = client_for(admin).get("/api/reports/detailed/")

    assert response.status_code == 200
    row = next(item for item in response.json() if item["id"] == issue.pk)
    assert row["issue_officer"] == officer_a.username
