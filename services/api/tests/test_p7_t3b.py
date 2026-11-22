"""P7-T3b regression coverage for quarantine and action comments."""

import importlib

import pytest
from django.apps import apps
from django.core.files.uploadedfile import SimpleUploadedFile

from domains.attachments.models import Attachment
from domains.issues.models import Issue, IssueStatus
from domains.products.models import Product

from .conftest import client_for

pytestmark = pytest.mark.django_db


@pytest.fixture
def issue(bank_a, officer_a):
    return Issue.objects.create(
        organization=bank_a,
        created_by=officer_a,
        submitted_by=officer_a,
        status=IssueStatus.SUBMITTED,
        title="Synthetic P7-T3b issue",
        reference="SR-P7-T3B",
    )


def post_action(issue, actor, action, fields):
    issue.refresh_from_db()
    response = client_for(actor).post(
        f"/api/issues/{issue.pk}/{action}/",
        {"version": issue.version, "comment": f"comment for {action}", **fields},
        format="json",
    )
    assert response.status_code == 200, response.content
    issue.refresh_from_db()


def test_every_workflow_action_persists_optional_comment(
    issue, officer_a, support, make_user, bank_a
):
    verifier = make_user("t3b_verifier", bank_a, "ISSUE_VERIFIER")
    events = []

    # Submission has no version and is the only action on a draft.
    issue.product = Product.objects.create(name="Synthetic P7-T3b product")
    issue.description = "Synthetic submission details"
    issue.request_type = "SUPPORT"
    issue.priority = "MEDIUM"
    issue.status = IssueStatus.DRAFT
    issue.submitted_by = None
    issue.save(
        update_fields=[
            "product",
            "description",
            "request_type",
            "priority",
            "status",
            "submitted_by",
        ]
    )
    response = client_for(officer_a).post(
        f"/api/issues/{issue.pk}/submit/", {"comment": "comment for submit"}, format="json"
    )
    assert response.status_code == 200, response.content
    events.append(("SUBMITTED", "submit"))

    post_action(issue, support, "accept", {"tentative_delivery_later": True})
    events.append(("ACCEPTED", "accept"))
    post_action(issue, support, "revise-date", {"tentative_delivery_date": "2027-01-15"})
    events.append(("TENTATIVE_DATE_REVISED", "revise-date"))
    post_action(issue, support, "assign", {"assignee": support.pk})
    events.append(("ASSIGNED", "assign"))
    post_action(issue, support, "start", {})
    events.append(("STARTED", "start"))
    post_action(issue, support, "deliver", {"delivery_note": "Fixed", "deployment_details": "v1"})
    events.append(("DELIVERED", "deliver"))
    post_action(issue, verifier, "verify", {})
    events.append(("VERIFIED", "verify"))
    post_action(issue, support, "close", {})
    events.append(("CLOSED", "close"))
    post_action(issue, officer_a, "reopen", {"reason": "Synthetic regression"})
    events.append(("REOPENED", "reopen"))

    for kind, action in events:
        assert issue.events.get(kind=kind).details["comment"] == f"comment for {action}"


def test_reject_and_failed_verification_actions_persist_comments(issue, support, bank_a, make_user):
    response = client_for(support).post(
        f"/api/issues/{issue.pk}/reject/",
        {"version": issue.version, "reason": "Cannot reproduce", "comment": "reject note"},
        format="json",
    )
    assert response.status_code == 200
    assert issue.events.get(kind="REJECTED").details["comment"] == "reject note"

    issue.status = IssueStatus.AWAITING_VERIFICATION
    issue.version += 1
    issue.save(update_fields=["status", "version"])
    verifier = make_user("t3b_verifier_fail", bank_a, "ISSUE_VERIFIER")
    response = client_for(verifier).post(
        f"/api/issues/{issue.pk}/fail-verification/",
        {
            "version": issue.version,
            "reason": "Still broken",
            "comment": "verification failure note",
        },
        format="json",
    )
    assert response.status_code == 200
    assert issue.events.get(kind="VERIFICATION_FAILED").details["comment"] == (
        "verification failure note"
    )


def test_non_utf8_text_upload_is_rejected_without_partial_attachment(issue, officer_a):
    response = client_for(officer_a).post(
        f"/api/issues/{issue.pk}/attachments/",
        {"file": SimpleUploadedFile("bad.txt", b"synthetic\xffdata")},
        format="multipart",
    )
    assert response.status_code == 400
    assert Attachment.objects.filter(issue=issue).count() == 0


def test_non_clean_attachment_download_returns_locked(issue, officer_a):
    attachment = Attachment.objects.create(
        issue=issue,
        file=SimpleUploadedFile("quarantined.txt", b"synthetic evidence"),
        original_name="quarantined.txt",
        content_type="text/plain",
        size=18,
        uploaded_by=officer_a,
        quarantine_status="QUARANTINED",
    )
    response = client_for(officer_a).get(f"/api/attachments/{attachment.pk}/download/")
    assert response.status_code == 423


def test_rejected_file_metadata_is_hidden_from_other_bank_user(issue, officer_a, bank_a, make_user):
    peer = make_user("t3b_peer", bank_a, "ISSUE_OFFICER")
    response = client_for(officer_a).post(
        f"/api/issues/{issue.pk}/attachments/",
        {"file": SimpleUploadedFile("eicar.txt", b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE")},
        format="multipart",
    )
    assert response.status_code == 201
    assert response.data["quarantine_status"] == "REJECTED"
    assert client_for(peer).get(f"/api/issues/{issue.pk}/attachments/").json() == []


def test_legacy_quarantined_attachments_are_rescanned(issue, officer_a):
    legacy_clean = Attachment.objects.create(
        issue=issue,
        file=SimpleUploadedFile("legacy.txt", b"synthetic legacy evidence"),
        original_name="legacy.txt",
        content_type="text/plain",
        size=25,
        uploaded_by=officer_a,
        quarantine_status="QUARANTINED",
    )
    legacy_rejected = Attachment.objects.create(
        issue=issue,
        file=SimpleUploadedFile("legacy-eicar.txt", b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE"),
        original_name="legacy-eicar.txt",
        content_type="text/plain",
        size=35,
        uploaded_by=officer_a,
        quarantine_status="QUARANTINED",
    )
    migration = importlib.import_module(
        "domains.attachments.migrations.0003_rescan_legacy_quarantine"
    )
    migration.rescan_legacy_quarantined(apps, None)
    legacy_clean.refresh_from_db()
    legacy_rejected.refresh_from_db()
    assert legacy_clean.quarantine_status == "CLEAN"
    assert legacy_rejected.quarantine_status == "REJECTED"
    assert not legacy_rejected.file
