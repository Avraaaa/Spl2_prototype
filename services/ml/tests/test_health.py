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


def test_semantic_rank_is_controlled_when_local_model_is_disabled(monkeypatch):
    monkeypatch.delenv("ML_MODEL_ENABLED", raising=False)
    monkeypatch.setenv("ML_SHARED_TOKEN", "synthetic-token")
    response = client.post(
        "/internal/rank",
        headers={"X-Service-Token": "synthetic-token"},
        json={"query": "login timeout", "candidates": ["authentication timeout"]},
    )
    assert response.status_code == 503
