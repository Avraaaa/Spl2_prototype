"""Synthetic demo seed is idempotent, DEBUG-only and produces a usable role matrix."""

import pytest
from django.contrib.auth.models import User
from django.core.management import CommandError, call_command

from domains.tenants.models import Organization

from .conftest import login

pytestmark = pytest.mark.django_db


def test_seed_is_idempotent_and_covers_roles(settings):
    settings.DEBUG = True
    call_command("seed_demo")
    call_command("seed_demo")
    assert Organization.objects.filter(kind="BANK").count() == 2
    assert Organization.objects.filter(kind="DATASOFT").count() == 1
    dual = User.objects.get(username="nwd.dual")
    assert sorted(m.role for m in dual.memberships.all()) == ["ISSUE_OFFICER", "ISSUE_VERIFIER"]
    client, response = login("ds.admin", "Demo-Pass-2026!")
    assert response.status_code == 200
    assert response.json()["roles"] == ["DATASOFT_ADMIN"]


def test_seed_refuses_without_debug(settings):
    settings.DEBUG = False
    with pytest.raises(CommandError):
        call_command("seed_demo")
