"""Administrator audit viewer API behavior."""

import pytest

from domains.audit.models import AuditRecord
from domains.audit.services import append_record

from .conftest import client_for

pytestmark = pytest.mark.django_db


def test_admin_can_filter_records_and_view_integrity_by_bank(admin, officer_a, officer_b):
    first = append_record(
        organization=officer_a.account.organization,
        actor=officer_a,
        action="issue.submitted",
        payload={"reference": "SR-1001"},
    )
    append_record(
        organization=officer_b.account.organization,
        actor=officer_b,
        action="issue.accepted",
        payload={"reference": "SR-2001"},
    )

    response = client_for(admin).get(
        "/api/audit/records/",
        {"organization": "NWD", "action": "submitted", "ordering": "-created_at"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["results"][0]["id"] == first.pk
    assert body["results"][0]["organization_code"] == "NWD"
    assert len(body["results"]) == 1
    assert body["integrity"] == {"valid": True, "first_invalid_sequence": None}


def test_admin_can_export_filtered_records_as_csv(admin, officer_a, officer_b):
    append_record(
        organization=officer_a.account.organization,
        actor=officer_a,
        action="issue.submitted",
        payload={"reference": "SR-1002"},
    )
    append_record(
        organization=officer_b.account.organization,
        actor=officer_b,
        action="issue.accepted",
        payload={"reference": "SR-2002"},
    )

    response = client_for(admin).get("/api/audit/records/export/", {"organization": "NWD"})

    assert response.status_code == 200
    assert "text/csv" in response["Content-Type"]
    assert "SR-1002" in response.content.decode()
    assert "SR-2002" not in response.content.decode()


@pytest.mark.parametrize("url", ["/api/audit/records/", "/api/audit/records/export/"])
def test_bank_user_cannot_list_or_export_audit_records(url, officer_a):
    assert client_for(officer_a).get(url).status_code == 403


def test_support_agent_cannot_list_or_export_audit_records(support):
    assert client_for(support).get("/api/audit/records/").status_code == 403
    assert client_for(support).get("/api/audit/records/export/").status_code == 403


def test_audit_viewer_does_not_modify_or_delete_records(admin, officer_a):
    record = append_record(
        organization=officer_a.account.organization,
        actor=officer_a,
        action="issue.submitted",
        payload={},
    )
    before = AuditRecord.objects.count()

    patch_response = client_for(admin).patch(f"/api/audit/records/{record.pk}/", {}, format="json")
    assert patch_response.status_code == 405
    assert client_for(admin).delete(f"/api/audit/records/{record.pk}/").status_code == 405
    assert AuditRecord.objects.count() == before
