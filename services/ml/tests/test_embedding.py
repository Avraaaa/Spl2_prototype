import pytest

from app.embedding import load_local_sentence_transformer


def test_offline_embedding_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ML_MODEL_ENABLED", raising=False)
    with pytest.raises(RuntimeError, match="disabled"):
        load_local_sentence_transformer()
