import pytest

from domains.issues.models import Issue
from domains.products.models import Product

from .conftest import client_for
from .test_n_06 import payload

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("sensitive_text", "masked_text"),
    [
        ("OTP for transfer is 123456", "OTP for transfer is [OTP REDACTED]"),
        ("Use 123456 as your OTP.", "Use [OTP REDACTED] as your OTP."),
    ],
)
def test_contextual_otp_is_masked_on_draft_create_and_edit(officer_a, sensitive_text, masked_text):
    product = Product.objects.create(name="Synthetic Core")
    client = client_for(officer_a)
    created = client.post(
        "/api/issues/",
        payload(product.pk) | {"description": sensitive_text},
        format="json",
    )

    assert created.status_code == 201, created.content
    issue_id = created.json()["id"]
    assert created.json()["description"] == masked_text
    assert Issue.objects.get(pk=issue_id).description == masked_text

    edited = client.patch(f"/api/issues/{issue_id}/", {"title": sensitive_text}, format="json")

    assert edited.status_code == 200, edited.content
    assert edited.json()["title"] == masked_text
    assert Issue.objects.get(pk=issue_id).title == masked_text
