"""Regression tests for private attachment content validation."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from domains.issues.models import Issue, IssueStatus

from .conftest import client_for

pytestmark = pytest.mark.django_db


def test_text_upload_checks_content_beyond_the_first_eight_kilobytes(
    bank_a, officer_a, settings, tmp_path
):
    settings.MEDIA_ROOT = tmp_path
    issue = Issue.objects.create(
        organization=bank_a,
        created_by=officer_a,
        submitted_by=officer_a,
        status=IssueStatus.SUBMITTED,
        title="Full attachment validation",
        reference="SR-9911",
    )
    disguised_binary = b"safe text\n" + b"x" * 8192 + b"\x00binary tail"

    response = client_for(officer_a).post(
        f"/api/issues/{issue.pk}/attachments/",
        {"file": SimpleUploadedFile("late-binary.log", disguised_binary)},
        format="multipart",
    )

    assert response.status_code == 400
    assert "does not match" in str(response.data).lower()
