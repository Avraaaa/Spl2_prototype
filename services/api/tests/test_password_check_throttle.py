"""P1-T1b / N-01: password re-entry has a shared, per-user rate limit."""

import pytest
from django.conf import settings
from django.contrib.auth.models import User

from .conftest import client_for

pytestmark = pytest.mark.django_db

WRONG_PASSWORD = "Definitely-Wrong-2026!"
PASSWORD_CHECK_LIMIT = settings.PASSWORD_CHECK_RATE_PER_MINUTE


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        (
            "/api/auth/change-username/",
            {"username": "new_officer", "current_password": WRONG_PASSWORD},
        ),
        (
            "/api/auth/change-password/",
            {"current_password": WRONG_PASSWORD, "new_password": "Another-Strong-Pass-77"},
        ),
    ],
)
def test_repeated_wrong_passwords_are_throttled_per_user(
    officer_a: User, officer_b: User, path: str, payload: dict[str, str]
) -> None:
    first_user = client_for(officer_a)
    for _ in range(PASSWORD_CHECK_LIMIT):
        response = first_user.post(path, payload, format="json")
        assert response.status_code == 400, response.content
    assert first_user.post(path, payload, format="json").status_code == 429
    assert client_for(officer_b).post(path, payload, format="json").status_code == 400


def test_username_and_password_changes_share_password_check_budget(officer_a: User) -> None:
    client = client_for(officer_a)
    username_payload = {"username": "new_officer", "current_password": WRONG_PASSWORD}
    password_payload = {
        "current_password": WRONG_PASSWORD,
        "new_password": "Another-Strong-Pass-77",
    }
    for index in range(PASSWORD_CHECK_LIMIT):
        path, payload = (
            ("/api/auth/change-username/", username_payload)
            if index % 2 == 0
            else ("/api/auth/change-password/", password_payload)
        )
        assert client.post(path, payload, format="json").status_code == 400
    assert (
        client.post("/api/auth/change-username/", username_payload, format="json").status_code
        == 429
    )
    assert (
        client.post("/api/auth/change-password/", password_payload, format="json").status_code
        == 429
    )
