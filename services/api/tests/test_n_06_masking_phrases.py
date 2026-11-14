import pytest

from domains.issues.models import Issue
from domains.products.models import Product

from .conftest import client_for
from .test_n_06 import payload

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("sensitive_text", "masked_text"),
    [
        ("OTP code is 123456", "OTP code is [OTP REDACTED]"),
        ("one-time passcode: 123456", "one-time passcode: [OTP REDACTED]"),
        ("verification code 123456", "verification code [OTP REDACTED]"),
        ("Card 1234 5678 9012 3456", "Card [CARD REDACTED]"),
    ],
)
def test_common_codes_and_spaced_cards_are_masked_before_save(
    officer_a, sensitive_text, masked_text
):
    product = Product.objects.create(name="Synthetic Core")
    response = client_for(officer_a).post(
        "/api/issues/",
        payload(product.pk) | {"description": sensitive_text},
        format="json",
    )

    assert response.status_code == 201, response.content
    assert response.json()["description"] == masked_text
    assert Issue.objects.get(pk=response.json()["id"]).description == masked_text
