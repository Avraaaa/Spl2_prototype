from fastapi.testclient import TestClient

from app.main import app
from app.masking import mask_text

client = TestClient(app)


def test_health() -> None:
    assert client.get("/health").status_code == 200


def test_private_endpoint_rejects_untrusted_call() -> None:
    assert client.post("/internal/mask", json={"text": "demo"}).status_code == 403


def test_synthetic_otp() -> None:
    assert "123456" not in mask_text("OTP: 123456 failed")
