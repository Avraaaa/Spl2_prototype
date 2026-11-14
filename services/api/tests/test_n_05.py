import pytest

from domains.products.models import Product

from .conftest import client_for

pytestmark = pytest.mark.django_db


def test_products_admin_managed_and_readable_by_officer(admin, officer_a):
    administrator = client_for(admin)
    created = administrator.post("/api/admin/products/", {"name": "Synthetic Core"}, format="json")
    assert created.status_code == 201
    product = created.json()
    module = administrator.post(
        f"/api/admin/products/{product['id']}/modules/", {"name": "Ledger"}, format="json"
    )
    assert module.status_code == 201
    assert client_for(officer_a).get("/api/products/").json()[0]["modules"][0]["name"] == "Ledger"
    assert client_for(officer_a).post("/api/admin/products/", {"name": "No"}).status_code == 403
    assert Product.objects.count() == 1
