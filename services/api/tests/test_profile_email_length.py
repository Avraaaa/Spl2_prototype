"""P1-T1b / N-01: profile email validation matches the User column."""

import pytest

from domains.accounts.models import AccountEvent

from .conftest import client_for

pytestmark = pytest.mark.django_db


def test_profile_email_accepts_254_characters_and_rejects_255(officer_a):
    client = client_for(officer_a)
    valid_email = f"{'a' * 64}@{'b' * 63}.{'c' * 63}.{'d' * 61}"
    too_long_email = valid_email + "d"
    assert len(valid_email) == 254
    assert len(too_long_email) == 255

    accepted = client.patch("/api/auth/me/", {"email": valid_email}, format="json")
    assert accepted.status_code == 200, accepted.content
    assert accepted.json()["email"] == valid_email

    rejected = client.patch("/api/auth/me/", {"email": too_long_email}, format="json")
    assert rejected.status_code == 400, rejected.content
    assert "email" in rejected.json()
    officer_a.refresh_from_db()
    assert officer_a.email == valid_email
    assert AccountEvent.objects.filter(subject=officer_a, kind="PROFILE_UPDATED").count() == 1
