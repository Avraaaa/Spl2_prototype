import pytest

from domains.products.models import Product

from .conftest import client_for
from .test_n_06 import payload

pytestmark = pytest.mark.django_db


def test_references_are_permanent_and_unique(officer_a):
    product = Product.objects.create(name="Synthetic Core")
    client = client_for(officer_a)
    first = client.post("/api/issues/", payload(product.pk), format="json").json()
    second = client.post("/api/issues/", payload(product.pk), format="json").json()
    assert first["reference"] != second["reference"]
    assert (
        client.patch(f"/api/issues/{first['id']}/", {"title": "Edited"}, format="json").json()[
            "reference"
        ]
        == first["reference"]
    )
