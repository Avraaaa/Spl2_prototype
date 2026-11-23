"""Opt-in offline encoder adapter, not yet connected to a business endpoint.

Sentence-Transformers remains an explicit requirement of the eventual ML feature.
P5 must pin model revision, embedding dimensions, hardware and benchmark scores.
This code requires the optional requirements-model.txt environment.
"""

import os
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def load_local_sentence_transformer():
    if os.environ.get("ML_MODEL_ENABLED") != "1":
        raise RuntimeError("ML inference disabled by default")
    models_dir = Path(
        os.environ.get("ML_MODELS_DIR", Path(__file__).resolve().parents[3] / "models")
    ).resolve()
    path = Path(os.environ.get("ML_MODEL_PATH", models_dir / "multilingual-e5-small")).resolve()
    if not path.is_dir():
        raise RuntimeError("Local model directory is missing; runtime downloads are forbidden")
    from sentence_transformers import SentenceTransformer  # optional heavy dependency

    trust_remote_code = path.name == "gte-multilingual-base" and path.is_relative_to(models_dir)
    return SentenceTransformer(
        str(path), local_files_only=True, trust_remote_code=trust_remote_code
    )
