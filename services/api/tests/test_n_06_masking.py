import pytest

from domains.issues.models import Issue
from domains.products.models import Product

from .conftest import client_for
from .test_n_06 import payload

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("sensitive_text", "masked_text"),
    [
        ("OTP is 123456", "OTP is [OTP REDACTED]"),
        ("Card 1234.5678.9012.3456", "Card [CARD REDACTED]"),
    ],
)
def test_draft_description_is_masked_before_persistence(officer_a, sensitive_text, masked_text):
    product = Product.objects.create(name="Synthetic Core")
    response = client_for(officer_a).post(
        "/api/issues/",
        payload(product.pk) | {"description": sensitive_text},
        format="json",
    )

    assert response.status_code == 201, response.content
    assert response.json()["description"] == masked_text
    assert Issue.objects.get(pk=response.json()["id"]).description == masked_text


def test_draft_edit_masks_sensitive_description_before_persistence(officer_a):
    product = Product.objects.create(name="Synthetic Core")
    client = client_for(officer_a)
    draft = client.post("/api/issues/", payload(product.pk), format="json").json()

    response = client.patch(
        f"/api/issues/{draft['id']}/",
        {"description": "OTP is 123456; card 1234.5678.9012.3456"},
        format="json",
    )

    assert response.status_code == 200, response.content
    assert response.json()["description"] == "OTP is [OTP REDACTED]; card [CARD REDACTED]"
    assert Issue.objects.get(pk=draft["id"]).description == response.json()["description"]


@pytest.mark.parametrize(
    ("sensitive_text", "expected", "raw_token"),
    [
        ("OTP: 123456", "OTP: [OTP REDACTED]", "123456"),
        ("OTP is 123456", "OTP is [OTP REDACTED]", "123456"),
        ("OTP for transfer: 123456", "OTP for transfer: [OTP REDACTED]", "123456"),
        ("OTP for transfer is 123456", "OTP for transfer is [OTP REDACTED]", "123456"),
        ("Use 123456 as your OTP", "Use [OTP REDACTED] as your OTP", "123456"),
        ("123456 is the OTP", "[OTP REDACTED] is the OTP", "123456"),
        (
            "the one-time password sent was 4821",
            "the one-time password sent was [OTP REDACTED]",
            "4821",
        ),
        ("PIN 4321", "PIN [OTP REDACTED]", "4321"),
        ("my tpin=9988", "my tpin=[OTP REDACTED]", "9988"),
        ("my mpin=9988", "my mpin=[OTP REDACTED]", "9988"),
        ("security code 77881", "security code [OTP REDACTED]", "77881"),
        ("passcode 77881", "passcode [OTP REDACTED]", "77881"),
        ("one time password 4821", "one time password [OTP REDACTED]", "4821"),
        ("one-time code 4821", "one-time code [OTP REDACTED]", "4821"),
        ("verification code 77881", "verification code [OTP REDACTED]", "77881"),
        ("ওটিপি ১২৩৪৫৬", "ওটিপি [OTP REDACTED]", "১২৩৪৫৬"),
        ("পিন ১২৩৪", "পিন [OTP REDACTED]", "১২৩৪"),
        ("ভেরিফিকেশন কোড ১২৩৪", "ভেরিফিকেশন কোড [OTP REDACTED]", "১২৩৪"),
        (
            "OTP" + " " * 40 + "123456",
            "OTP" + " " * 40 + "[OTP REDACTED]",
            "123456",
        ),
        ("card 4111 1111 1111 1111", "card [CARD REDACTED]", "4111 1111 1111 1111"),
        ("card 4111.1111.1111.1111", "card [CARD REDACTED]", "4111.1111.1111.1111"),
        ("card 4111-1111-1111-1111", "card [CARD REDACTED]", "4111-1111-1111-1111"),
    ],
)
def test_sensitive_text_is_masked_on_create_and_edit(
    officer_a, sensitive_text, expected, raw_token
):
    product = Product.objects.create(name="Synthetic Core")
    client = client_for(officer_a)
    created = client.post(
        "/api/issues/", payload(product.pk) | {"description": sensitive_text}, format="json"
    )

    assert created.status_code == 201, created.content
    issue_id = created.json()["id"]
    assert created.json()["description"] == expected
    assert Issue.objects.get(pk=issue_id).description == expected
    assert raw_token not in created.json()["description"]
    assert raw_token not in created.content.decode()

    edited = client.patch(f"/api/issues/{issue_id}/", {"title": sensitive_text}, format="json")

    assert edited.status_code == 200, edited.content
    assert edited.json()["title"] == expected
    assert Issue.objects.get(pk=issue_id).title == expected
    assert raw_token not in edited.json()["title"]
    assert raw_token not in edited.content.decode()


@pytest.mark.parametrize(
    "text",
    [
        "Error 4012 on the transfer screen",
        "Release version 2024 fails",
        "Transaction 98765 failed. OTP was not sent",
        "error code 5001",
        "Account branch 1234 in the report header",
        "OTP was not sent! 123456 appeared elsewhere",
        "OTP was not sent? 123456 appeared elsewhere",
        "OTP was not sent। ১২৩৪৫৬ appeared elsewhere",
        "OTP was not sent\n123456 appeared elsewhere",
        (
            "OTP followed by a very long unrelated description "
            "that goes far beyond forty characters 123456"
        ),
        "OTP abc123456def is malformed",
        "OTP" + " " * 41 + "123456",
    ],
)
def test_unrelated_numbers_remain_on_create_and_edit(officer_a, text):
    product = Product.objects.create(name="Synthetic Core")
    client = client_for(officer_a)
    created = client.post(
        "/api/issues/", payload(product.pk) | {"description": text}, format="json"
    )

    assert created.status_code == 201, created.content
    issue_id = created.json()["id"]
    assert created.json()["description"] == text
    assert Issue.objects.get(pk=issue_id).description == text

    edited = client.patch(f"/api/issues/{issue_id}/", {"title": text}, format="json")

    assert edited.status_code == 200, edited.content
    assert edited.json()["title"] == text
    assert Issue.objects.get(pk=issue_id).title == text


def test_expanded_masked_title_is_rejected_on_create(officer_a):
    product = Product.objects.create(name="Synthetic Core")
    title = "OTP 1234 " * 20
    assert len(title) <= 200

    response = client_for(officer_a).post(
        "/api/issues/", payload(product.pk) | {"title": title}, format="json"
    )

    assert response.status_code == 400, response.content
    assert "title" in response.json()
    assert not Issue.objects.exists()
    assert title not in response.content.decode()


def test_expanded_masked_title_is_rejected_on_edit(officer_a):
    product = Product.objects.create(name="Synthetic Core")
    client = client_for(officer_a)
    draft = client.post("/api/issues/", payload(product.pk), format="json").json()
    title = "OTP 1234 " * 20
    assert len(title) <= 200

    response = client.patch(f"/api/issues/{draft['id']}/", {"title": title}, format="json")

    assert response.status_code == 400, response.content
    assert "title" in response.json()
    saved = Issue.objects.get(pk=draft["id"])
    assert saved.title == draft["title"]
    assert saved.version == draft["version"]
    assert title not in response.content.decode()
