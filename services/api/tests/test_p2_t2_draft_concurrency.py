"""Draft edits require the version the officer last read."""

import pytest

from domains.issues.models import Issue
from domains.products.models import Product

from .conftest import client_for
from .test_n_06 import payload

pytestmark = pytest.mark.django_db


def test_draft_patch_rejects_stale_version_without_overwriting_fields(officer_a):
    product = Product.objects.create(name="Synthetic Concurrency")
    client = client_for(officer_a)
    draft = client.post("/api/issues/", payload(product.pk), format="json").json()
    path = f"/api/issues/{draft['id']}/"

    fresh = client.patch(
        path,
        {"version": draft["version"], "title": "First synthetic edit"},
        format="json",
    )
    assert fresh.status_code == 200, fresh.content
    assert fresh.json()["version"] == draft["version"] + 1

    stale = client.patch(
        path,
        {
            "version": draft["version"],
            "title": "Stale synthetic edit",
            "description": "Stale description",
        },
        format="json",
    )
    assert stale.status_code == 409, stale.content
    assert "changed by someone else" in stale.json()["detail"]

    stored = Issue.objects.get(pk=draft["id"])
    assert stored.title == "First synthetic edit"
    assert stored.description == draft["description"]
    assert stored.version == fresh.json()["version"]


def test_draft_patch_without_version_keeps_existing_edit_behavior(officer_a):
    product = Product.objects.create(name="Synthetic Concurrency")
    client = client_for(officer_a)
    draft = client.post("/api/issues/", payload(product.pk), format="json").json()

    response = client.patch(
        f"/api/issues/{draft['id']}/", {"title": "Unversioned edit"}, format="json"
    )

    assert response.status_code == 200, response.content
    assert response.json()["title"] == "Unversioned edit"
    assert response.json()["version"] == draft["version"] + 1
    stored = Issue.objects.get(pk=draft["id"])
    assert stored.title == "Unversioned edit"
    assert stored.version == draft["version"] + 1
