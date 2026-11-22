import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from domains.accounts.roles import Role
from domains.attachments.models import Attachment
from domains.issues.models import Issue, IssueStatus

from .conftest import client_for

pytestmark = pytest.mark.django_db


@pytest.fixture
def submitted(bank_a, officer_a):
    return Issue.objects.create(
        organization=bank_a,
        created_by=officer_a,
        submitted_by=officer_a,
        status=IssueStatus.SUBMITTED,
        title="Synthetic issue",
        reference="SR-P3-1",
    )


def test_comments_scope_masking_and_draft(submitted, officer_a, officer_b, support):
    url = f"/api/issues/{submitted.pk}/comments/"
    created = client_for(officer_a).post(url, {"body": "OTP is 123456"}, format="json")
    assert created.status_code == 201
    assert "123456" not in str(created.data)
    assert client_for(support).get(url).status_code == 200
    assert client_for(officer_b).get(url).status_code == 404
    assert client_for(officer_b).post(url, {"body": "no"}, format="json").status_code == 404
    draft = Issue.objects.create(organization=submitted.organization, created_by=officer_a)
    draft_url = f"/api/issues/{draft.pk}/comments/"
    assert (
        client_for(officer_a).post(draft_url, {"body": "draft"}, format="json").status_code == 201
    )
    assert client_for(support).get(draft_url).status_code == 404


def test_notes_and_tasks_never_reach_bank(submitted, officer_a, officer_b, support):
    staff = client_for(support)
    issue_url = f"/api/issues/{submitted.pk}/"
    task = staff.post(
        "/api/tasks/", {"issue": submitted.pk, "title": "Fix synthetic bug"}, format="json"
    )
    assert task.status_code == 201
    task_id = task.data["id"]
    assert (
        staff.post(f"{issue_url}internal-notes/", {"body": "secret"}, format="json").status_code
        == 201
    )
    assert (
        staff.post(
            f"/api/tasks/{task_id}/notes/", {"body": "commit secret"}, format="json"
        ).status_code
        == 201
    )
    bank = client_for(officer_a)
    assert bank.get(issue_url).status_code == 200
    assert "secret" not in str(bank.get(issue_url).data)
    assert "Fix synthetic bug" not in str(bank.get(issue_url).data)
    assert "secret" not in str(bank.get(f"{issue_url}comments/").data)
    assert "Fix synthetic bug" not in str(bank.get(f"{issue_url}attachments/").data)
    assert bank.get(f"{issue_url}internal-notes/").status_code == 403
    assert bank.get("/api/tasks/").status_code == 403
    assert bank.get(f"/api/tasks/{task_id}/").status_code == 403
    assert bank.get(f"/api/tasks/{task_id}/notes/").status_code == 403
    assert client_for(officer_b).get(issue_url).status_code == 404


def test_tasks_board_git_validation_and_scope(submitted, officer_a, support):
    staff = client_for(support)
    url = "/api/tasks/"
    bad = {"issue": submitted.pk, "title": "A", "commit_url": "http://bad"}
    assert staff.post(url, bad, format="json").status_code == 400
    good = {"issue": submitted.pk, "title": "A", "commit_url": "https://git.example/commit/1"}
    made = staff.post(url, good, format="json")
    assert made.status_code == 201
    task_id = made.data["id"]
    assert (
        staff.patch(f"{url}{task_id}/", {"assignee": officer_a.pk}, format="json").status_code
        == 403
    )
    moved = staff.patch(f"{url}{task_id}/", {"status": "in_progress"}, format="json")
    assert moved.status_code == 200
    assert moved.data["status"] == "in_progress"
    assert any(row["id"] == task_id for row in staff.get(url).data)
    assert client_for(officer_a).get(url).status_code == 403


def test_private_file_validation_and_two_bank_download(
    submitted, officer_a, officer_b, support, settings, tmp_path
):
    settings.MEDIA_ROOT = tmp_path
    issue_url = f"/api/issues/{submitted.pk}/"
    bank = client_for(officer_a)
    upload = bank.post(
        f"{issue_url}attachments/",
        {"file": SimpleUploadedFile("trace.txt", b"synthetic log\n", content_type="text/plain")},
        format="multipart",
    )
    assert upload.status_code == 201
    file_id = upload.data["id"]
    assert upload.data["quarantine_status"] == "CLEAN"
    assert "url" not in upload.data
    stored = Attachment.objects.get(pk=file_id)
    assert stored.file.name.startswith("private/")
    assert "trace" not in stored.file.name
    assert bank.get(f"/api/attachments/{file_id}/download/").status_code == 200
    assert client_for(officer_b).get(f"/api/attachments/{file_id}/download/").status_code == 404
    assert client_for(officer_b).get(f"{issue_url}attachments/").status_code == 404
    assert client_for(support).get(f"/api/attachments/{file_id}/download/").status_code == 200
    bad = bank.post(
        f"{issue_url}attachments/",
        {"file": SimpleUploadedFile("fake.png", b"not an image", content_type="image/png")},
        format="multipart",
    )
    assert bad.status_code == 400
    forbidden = bank.post(
        f"{issue_url}attachments/",
        {"file": SimpleUploadedFile("script.exe", b"MZ fake")},
        format="multipart",
    )
    assert forbidden.status_code == 400
    huge = bank.post(
        f"{issue_url}attachments/",
        {"file": SimpleUploadedFile("huge.txt", b"x" * (10 * 1024 * 1024 + 1))},
        format="multipart",
    )
    assert huge.status_code == 400


def test_comment_attachment_scope(submitted, officer_a, officer_b, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    bank = client_for(officer_a)
    comment = bank.post(
        f"/api/issues/{submitted.pk}/comments/", {"body": "Evidence"}, format="json"
    ).data
    response = bank.post(
        f"/api/issues/{submitted.pk}/attachments/",
        {"comment": comment["id"], "file": SimpleUploadedFile("evidence.csv", b"a,b\n1,2\n")},
        format="multipart",
    )
    assert response.status_code == 201
    assert response.data["comment"] == comment["id"]
    assert (
        client_for(officer_b).get(f"/api/attachments/{response.data['id']}/download/").status_code
        == 404
    )


def test_verifier_can_comment_after_submission(submitted, bank_a, make_user):
    verifier = make_user("verifier_p3", bank_a, Role.ISSUE_VERIFIER)
    url = f"/api/issues/{submitted.pk}/comments/"
    assert (
        client_for(verifier).post(url, {"body": "Verified evidence"}, format="json").status_code
        == 201
    )


def test_delete_draft_with_comment(bank_a, officer_a, officer_b):
    draft = Issue.objects.create(organization=bank_a, created_by=officer_a)
    url = f"/api/issues/{draft.pk}/"
    bank = client_for(officer_a)
    assert (
        bank.post(f"{url}comments/", {"body": "Draft question"}, format="json").status_code == 201
    )
    assert client_for(officer_b).delete(url).status_code == 404
    assert bank.delete(url).status_code == 204
    assert not Issue.objects.filter(pk=draft.pk).exists()


def test_delete_draft_with_attachment_and_comment(
    bank_a, officer_a, settings, tmp_path, django_capture_on_commit_callbacks
):
    settings.MEDIA_ROOT = tmp_path
    draft = Issue.objects.create(organization=bank_a, created_by=officer_a)
    url = f"/api/issues/{draft.pk}/"
    bank = client_for(officer_a)
    comment = bank.post(f"{url}comments/", {"body": "Draft evidence"}, format="json")
    assert comment.status_code == 201
    upload = bank.post(
        f"{url}attachments/",
        {
            "comment": comment.data["id"],
            "file": SimpleUploadedFile("evidence.txt", b"synthetic draft evidence\n"),
        },
        format="multipart",
    )
    assert upload.status_code == 201
    standalone = bank.post(
        f"{url}attachments/",
        {"file": SimpleUploadedFile("standalone.log", b"synthetic draft log\n")},
        format="multipart",
    )
    assert standalone.status_code == 201
    attachment = Attachment.objects.get(pk=upload.data["id"])
    stored_name = attachment.file.name
    standalone_file = Attachment.objects.get(pk=standalone.data["id"]).file
    assert attachment.file.storage.exists(stored_name)
    assert standalone_file.storage.exists(standalone_file.name)
    with django_capture_on_commit_callbacks(execute=True):
        assert bank.delete(url).status_code == 204
    assert not Issue.objects.filter(pk=draft.pk).exists()
    assert not Attachment.objects.filter(pk=attachment.pk).exists()
    assert not Attachment.objects.filter(pk=standalone.data["id"]).exists()
    assert not attachment.file.storage.exists(stored_name)
    assert not standalone_file.storage.exists(standalone_file.name)
