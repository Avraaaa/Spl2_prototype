import pytest

from .conftest import client_for

pytestmark = pytest.mark.django_db


def test_masking_preview_returns_safe_copy_without_raw_values(officer_a):
    response = client_for(officer_a).post(
        "/api/issues/masking-preview/",
        {
            "fields": {
                "description": "Account 1234567890 used OTP 123456 from 01712345678",
            }
        },
        format="json",
    )

    assert response.status_code == 200, response.content
    body = response.json()
    masked = body["masked_fields"]["description"]
    assert "1234567890" not in masked
    assert "123456" not in masked
    assert "01712345678" not in masked
    assert set(body["detected_types"]) == {"account", "otp", "phone"}


def test_masking_preview_rejects_unknown_fields(officer_a):
    response = client_for(officer_a).post(
        "/api/issues/masking-preview/",
        {"fields": {"password": "secret"}},
        format="json",
    )

    assert response.status_code == 400
