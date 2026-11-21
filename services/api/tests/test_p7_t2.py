"""P7-T2: tenant scoped deployed-version history and response deadlines."""

from datetime import timedelta

import pytest
from django.utils import timezone

from domains.issues.models import Issue
from domains.products.models import Module, Product

from .conftest import client_for

pytestmark = pytest.mark.django_db


def test_deployed_versions_are_tenant_scoped_and_admin_written(
    admin, officer_a, officer_b, bank_a, bank_b
):
    product = Product.objects.create(name="Synthetic Core")
    module = Module.objects.create(product=product, name="Ledger")
    path = "/api/deployed-versions/"
    response = client_for(admin).post(
        path,
        {
            "organization": bank_a.pk,
            "product": product.pk,
            "module": module.pk,
            "version": "2.4",
            "deployed_at": "2026-01-15",
        },
        format="json",
    )
    assert response.status_code == 201
    assert (
        client_for(admin)
        .post(
            path,
            {
                "organization": bank_b.pk,
                "product": product.pk,
                "version": "1.0",
                "deployed_at": "2026-02-01",
            },
            format="json",
        )
        .status_code
        == 201
    )
    assert client_for(officer_a).get(path).json()[0]["version"] == "2.4"
    assert client_for(officer_b).get(path).json()[0]["version"] == "1.0"
    assert client_for(officer_a).post(path, {}, format="json").status_code == 403


def test_priority_response_period_drives_overdue_and_edge_dates(admin, support, officer_a, bank_a):
    product = Product.objects.create(name="Synthetic Core")
    issue = Issue.objects.create(
        organization=bank_a,
        created_by=officer_a,
        product=product,
        priority="HIGH",
        status="SUBMITTED",
    )
    response = client_for(admin).put(
        "/api/admin/response-due-periods/", {"periods": {"HIGH": 3}}, format="json"
    )
    assert response.status_code == 200
    assert (
        client_for(officer_a).get("/api/reports/detailed/").json()[0]["response_due_date"]
        == (issue.created_at.date() + timedelta(days=3)).isoformat()
    )
    assert client_for(officer_a).get("/api/reports/detailed/?overdue=true").json() == []
    issue.created_at = timezone.now() - timedelta(days=4)
    issue.save(update_fields=["created_at"])
    assert (
        client_for(officer_a).get("/api/reports/detailed/?overdue=true").json()[0]["is_overdue"]
        is True
    )
    assert (
        client_for(support)
        .put("/api/admin/response-due-periods/", {"periods": {"HIGH": 3}}, format="json")
        .status_code
        == 403
    )
