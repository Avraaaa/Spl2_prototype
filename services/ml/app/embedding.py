"""Opt-in offline encoder adapter, not yet connected to a business endpoint.

Sentence-Transformers remains an explicit requirement of the eventual ML feature.
P5 must pin model revision, embedding dimensions, hardware and benchmark scores.
This code requires the optional requirements-model.txt environment.
"""

import os
from pathlib import Path


def load_local_sentence_transformer():
    if os.environ.get("ML_MODEL_ENABLED") != "1":
        raise RuntimeError("ML inference disabled by default")
    path = Path(os.environ.get("ML_MODEL_PATH", "/models/multilingual-e5-small"))
    if not path.is_dir():
        raise RuntimeError("Local model directory is missing; runtime downloads are forbidden")
    from sentence_transformers import SentenceTransformer  # optional heavy dependency

    return SentenceTransformer(str(path), local_files_only=True, trust_remote_code=False)
