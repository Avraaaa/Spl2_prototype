"""P4-T3 attachment formats and validation."""

from io import BytesIO
from zipfile import ZipFile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

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
        title="Synthetic office document upload",
        reference="SR-P4-T3",
    )


def office_file(name: str, directory: str, document: str) -> SimpleUploadedFile:
    payload = BytesIO()
    with ZipFile(payload, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr(f"{directory}/{document}", "<document />")
    return SimpleUploadedFile(name, payload.getvalue())


@pytest.mark.parametrize(
    ("name", "directory", "document", "content_type"),
    [
        (
            "evidence.docx",
            "word",
            "document.xml",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        (
            "transactions.xlsx",
            "xl",
            "workbook.xml",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
        (
            "release.pptx",
            "ppt",
            "presentation.xml",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ),
    ],
)
def test_common_office_documents_are_accepted(
    submitted_issue, officer_a, name, directory, document, content_type
):
    response = client_for(officer_a).post(
        f"/api/issues/{submitted_issue.pk}/attachments/",
        {"file": office_file(name, directory, document)},
        format="multipart",
    )

    assert response.status_code == 201
    assert response.data["content_type"] == content_type


def test_renamed_executable_is_not_accepted_as_office_document(submitted_issue, officer_a):
    response = client_for(officer_a).post(
        f"/api/issues/{submitted_issue.pk}/attachments/",
        {"file": SimpleUploadedFile("malware.docx", b"MZ synthetic executable")},
        format="multipart",
    )

    assert response.status_code == 400
    assert "does not match" in str(response.data).lower()


@pytest.mark.parametrize(
    "upload",
    [
        SimpleUploadedFile("empty.txt", b""),
        SimpleUploadedFile("too-large.txt", b"x" * (10 * 1024 * 1024 + 1)),
    ],
)
def test_empty_and_oversized_files_are_rejected(submitted_issue, officer_a, upload):
    response = client_for(officer_a).post(
        f"/api/issues/{submitted_issue.pk}/attachments/",
        {"file": upload},
        format="multipart",
    )

    assert response.status_code == 400
    assert "between 1 byte and 10 mb" in str(response.data).lower()
