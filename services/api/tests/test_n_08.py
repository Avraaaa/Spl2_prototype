import pytest

from domains.products.models import Module, Product

from .conftest import client_for
from .test_n_06 import payload

pytestmark = pytest.mark.django_db


def test_bug_evidence_required_for_submission(officer_a):
    product = Product.objects.create(name="Synthetic Core")
    data = payload(product.pk) | {"request_type": "BUG"}
    client = client_for(officer_a)
    issue = client.post("/api/issues/", data, format="json").json()
    assert client.post(f"/api/issues/{issue['id']}/submit/").status_code == 400
    evidence = {
        "environment": "Test",
        "steps_to_reproduce": "Open synthetic page",
        "expected_result": "Page loads",
        "actual_result": "Error appears",
    }
    assert client.patch(f"/api/issues/{issue['id']}/", evidence, format="json").status_code == 200
    assert client.post(f"/api/issues/{issue['id']}/submit/").status_code == 200


def test_module_must_belong_to_product(officer_a):
    product = Product.objects.create(name="Synthetic Core")
    other = Product.objects.create(name="Synthetic Other")
    module = Module.objects.create(product=other, name="Other Module")
    response = client_for(officer_a).post(
        "/api/issues/", payload(product.pk) | {"module": module.pk}, format="json"
    )
    assert response.status_code == 400
