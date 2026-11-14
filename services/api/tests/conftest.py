"""Shared synthetic fixtures: one DataSoft org and two client banks (A, B). No real data."""

from collections.abc import Callable
from typing import Any

import pytest
from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework.test import APIClient

from domains.accounts import services
from domains.accounts.roles import Role
from domains.tenants.models import Organization

PASSWORD = "Synthetic-Pass-2026!"


@pytest.fixture(autouse=True)
def _clear_throttle_cache() -> None:
    cache.clear()


@pytest.fixture(autouse=True)
def _fast_test_hasher(settings: Any) -> None:
    # Test-only speedup; production hashing settings are unchanged.
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture
def datasoft(db: Any) -> Organization:
    return services.ensure_datasoft_organization()


@pytest.fixture
def bank_a(db: Any) -> Organization:
    return Organization.objects.create(name="Northwind Demo Bank", code="NWD", kind="BANK")


@pytest.fixture
def bank_b(db: Any) -> Organization:
    return Organization.objects.create(name="Riverstone Demo Bank", code="RSD", kind="BANK")


@pytest.fixture
def make_user(db: Any) -> Callable[..., User]:
    def _make(username: str, org: Organization, *roles: Role, active_password: bool = True) -> User:
        user = services.create_user_unchecked(
            organization=org,
            username=username,
            email=f"{username}@example.test",
            full_name=username.title(),
            roles=list(roles),
        )
        if active_password:
            user.set_password(PASSWORD)
            user.save()
            user.account.must_change_password = False
            user.account.save()
        return user

    return _make


@pytest.fixture
def admin(datasoft: Organization, make_user: Callable[..., User]) -> User:
    return make_user("ds_admin", datasoft, Role.DATASOFT_ADMIN)


@pytest.fixture
def support(datasoft: Organization, make_user: Callable[..., User]) -> User:
    return make_user("ds_support", datasoft, Role.SUPPORT_AGENT)


@pytest.fixture
def officer_a(bank_a: Organization, make_user: Callable[..., User]) -> User:
    return make_user("officer_a", bank_a, Role.ISSUE_OFFICER)


@pytest.fixture
def officer_b(bank_b: Organization, make_user: Callable[..., User]) -> User:
    return make_user("officer_b", bank_b, Role.ISSUE_OFFICER)


def client_for(user: User | None = None) -> APIClient:
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


def login(username: str, password: str = PASSWORD) -> tuple[APIClient, Any]:
    """Real session login through the public endpoint (not force_authenticate)."""
    client = APIClient()
    response = client.post(
        "/api/auth/login/", {"username": username, "password": password}, format="json"
    )
    return client, response
