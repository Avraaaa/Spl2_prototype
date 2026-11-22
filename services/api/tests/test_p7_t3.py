"""P7-T3 workflow comments and attachment quarantine."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from domains.attachments.models import Attachment
from domains.issues.models import Issue, IssueStatus

from .conftest import client_for

pytestmark = pytest.mark.django_db


@pytest.fixture
def submitted_issue(bank_a, officer_a):
    return Issue.objects.create(
        organization=bank_a,
        created_by=officer_a,
        submitted_by=officer_a,
        status=IssueStatus.SUBMITTED,
        title="Synthetic quarantine check",
        reference="SR-P7-T3",
    )


def test_workflow_action_comment_is_stored_on_visible_event(submitted_issue, support):
    response = client_for(support).post(
        f"/api/issues/{submitted_issue.pk}/accept/",
        {
            "version": submitted_issue.version,
            "tentative_delivery_later": True,
            "comment": "Synthetic client-visible update",
        },
        format="json",
    )

    assert response.status_code == 200
    event = submitted_issue.events.get(kind="ACCEPTED")
    assert event.details["comment"] == "Synthetic client-visible update"


def test_comment_is_masked_before_event_persistence(submitted_issue, support):
    client_for(support).post(
        f"/api/issues/{submitted_issue.pk}/accept/",
        {
            "version": submitted_issue.version,
            "tentative_delivery_later": True,
            "comment": "OTP 123456",
        },
        format="json",
    )
    event = submitted_issue.events.get(kind="ACCEPTED")
    assert "123456" not in event.details["comment"]


def test_clean_attachment_can_be_downloaded_after_quarantine_scan(submitted_issue, officer_a):
    response = client_for(officer_a).post(
        f"/api/issues/{submitted_issue.pk}/attachments/",
        {"file": SimpleUploadedFile("evidence.txt", b"Synthetic evidence")},
        format="multipart",
    )

    assert response.status_code == 201
    attachment_id = response.data["id"]
    assert response.data["quarantine_status"] == "CLEAN"
    assert (
        client_for(officer_a).get(f"/api/attachments/{attachment_id}/download/").status_code == 200
    )


def test_eicar_upload_is_rejected(submitted_issue, officer_a):
    response = client_for(officer_a).post(
        f"/api/issues/{submitted_issue.pk}/attachments/",
        {
            "file": SimpleUploadedFile(
                "eicar.txt",
                b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*",
            )
        },
        format="multipart",
    )

    assert response.status_code == 201
    assert response.data["quarantine_status"] == "REJECTED"
    assert (
        client_for(officer_a).get(f"/api/attachments/{response.data['id']}/download/").status_code
        == 423
    )


def test_attachment_download_remains_tenant_scoped(submitted_issue, officer_a, officer_b):
    attachment = Attachment.objects.create(
        issue=submitted_issue,
        file=SimpleUploadedFile("evidence.txt", b"Synthetic evidence"),
        original_name="evidence.txt",
        content_type="text/plain",
        size=17,
        quarantine_status="CLEAN",
        uploaded_by=officer_a,
    )

    assert (
        client_for(officer_b).get(f"/api/attachments/{attachment.pk}/download/").status_code == 404
    )
