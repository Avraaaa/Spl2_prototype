import sys

from fastapi.testclient import TestClient

from app import embedding
from app import main as main_module
from app.main import app


def test_embedding_endpoint_reuses_model_loaded_at_startup(monkeypatch, tmp_path):
    model_path = tmp_path / "multilingual-e5-small"
    model_path.mkdir()
    monkeypatch.setenv("ML_MODEL_ENABLED", "1")
    monkeypatch.setenv("ML_MODEL_PATH", str(model_path))
    monkeypatch.setenv("ML_SHARED_TOKEN", "synthetic-token")
    embedding.load_local_sentence_transformer.cache_clear()
    constructions = []

    class FakeModel:
        def __init__(self, path, **kwargs):
            constructions.append(path)

        def encode(self, texts, normalize_embeddings):
            return [[1.0, 0.0] for _ in texts]

    class FakeSentenceTransformer:
        def __new__(cls, path, **kwargs):
            return FakeModel(path, **kwargs)

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        type("SentenceTransformers", (), {"SentenceTransformer": FakeSentenceTransformer}),
    )
    try:
        with TestClient(app) as client:
            headers = {"X-Service-Token": "synthetic-token"}
            for _ in range(3):
                response = client.post(
                    "/internal/embed", headers=headers, json={"texts": ["synthetic text"]}
                )
                assert response.status_code == 200
        assert len(constructions) == 1
    finally:
        embedding.load_local_sentence_transformer.cache_clear()


def test_startup_does_not_load_model_when_disabled(monkeypatch):
    monkeypatch.delenv("ML_MODEL_ENABLED", raising=False)
    monkeypatch.setenv("ML_SHARED_TOKEN", "synthetic-token")
    embedding.load_local_sentence_transformer.cache_clear()

    def fail_if_loaded():
        raise AssertionError("disabled startup attempted to load model")

    monkeypatch.setattr(main_module, "load_local_sentence_transformer", fail_if_loaded)
    with TestClient(app) as client:
        response = client.get(
            "/internal/embedding-readiness", headers={"X-Service-Token": "synthetic-token"}
        )
        assert response.status_code == 200
        assert response.json()["enabled"] is False
