import json

import pytest

from domains.issues.models import IssueStatus, RequestType
from domains.products.models import Product
from domains.search.models import Label

pytestmark = pytest.mark.django_db


def test_display_color_defaults_are_seeded(client, officer_a):
    client.force_login(officer_a)
    response = client.get("/api/display-colors/")
    assert response.status_code == 200
    payload = response.json()
    assert set(payload["request_types"]) == set(RequestType.values)
    assert set(payload["statuses"]) == set(IssueStatus.values)


def test_admin_can_update_type_status_and_entity_colors(client, admin):
    label = Label.objects.create(name="Color test")
    product = Product.objects.create(name="Color product")
    client.force_login(admin)
    assert (
        client.patch(
            f"/api/search/labels/{label.pk}/",
            json.dumps({"color": "#112233"}),
            content_type="application/json",
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/admin/products/{product.pk}/",
            json.dumps({"color": "#223344"}),
            content_type="application/json",
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/api/display-colors/request_type/BUG/",
            json.dumps({"color": "#334455"}),
            content_type="application/json",
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/api/display-colors/status/UNKNOWN/",
            json.dumps({"color": "#334455"}),
            content_type="application/json",
        ).status_code
        == 400
    )
    colors = client.get("/api/display-colors/").json()
    assert colors["labels"][str(label.pk)] == "#112233"
    assert colors["products"][str(product.pk)] == "#223344"
    assert colors["request_types"]["BUG"] == "#334455"


def test_non_admin_cannot_change_colors_and_read_has_no_tenant_data(client, support, officer_a):
    label = Label.objects.create(name="Protected label")
    product = Product.objects.create(name="Protected product")
    client.force_login(officer_a)
    response = client.get("/api/display-colors/")
    assert response.status_code == 200
    assert "organizations" not in response.json()
    for user in (support, officer_a):
        client.force_login(user)
        assert (
            client.put(
                "/api/display-colors/status/CLOSED/",
                json.dumps({"color": "#112233"}),
                content_type="application/json",
            ).status_code
            == 403
        )
        assert (
            client.patch(
                f"/api/search/labels/{label.pk}/",
                json.dumps({"color": "#112233"}),
                content_type="application/json",
            ).status_code
            == 403
        )
        assert (
            client.patch(
                f"/api/admin/products/{product.pk}/",
                json.dumps({"color": "#112233"}),
                content_type="application/json",
            ).status_code
            == 403
        )


def test_invalid_color_and_unknown_key_are_rejected(client, admin):
    client.force_login(admin)
    assert (
        client.put(
            "/api/display-colors/status/CLOSED/",
            json.dumps({"color": "red"}),
            content_type="application/json",
        ).status_code
        == 400
    )
    assert (
        client.put(
            "/api/display-colors/status/UNKNOWN/",
            json.dumps({"color": "#112233"}),
            content_type="application/json",
        ).status_code
        == 400
    )
    label = Label.objects.create(name="Invalid color")
    assert (
        client.patch(
            f"/api/search/labels/{label.pk}/",
            json.dumps({"color": "bad"}),
            content_type="application/json",
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/admin/products/",
            json.dumps({"name": "Invalid product", "color": "blue"}),
            content_type="application/json",
        ).status_code
        == 400
    )
