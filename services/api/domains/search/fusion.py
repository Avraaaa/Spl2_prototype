"""Score normalisation and convex fusion for lexical and dense retrieval."""

import os
import unicodedata
from collections.abc import Mapping, Sequence


def normalise_lexical(scores: Sequence[float]) -> list[float]:
    """Min-max scale lexical scores; ties carry no discriminating evidence."""
    if not scores:
        return []
    low = min(scores)
    high = max(scores)
    if high == low:
        return [0.0 for _ in scores]
    return [(float(score) - low) / (high - low) for score in scores]


def normalise_dense(cosine: Sequence[float]) -> list[float]:
    """Map cosine similarity's fixed [-1, 1] range to [0, 1]."""
    return [min(1.0, max(0.0, (float(score) + 1.0) / 2.0)) for score in cosine]


def fuse(
    lexical: Mapping[int, float], dense: Mapping[int, float], alpha: float
) -> dict[int, float]:
    """Fuse scores for the union of candidates; absent evidence contributes zero."""
    weight = min(1.0, max(0.0, float(alpha)))
    return {
        key: weight * dense.get(key, 0.0) + (1.0 - weight) * lexical.get(key, 0.0)
        for key in lexical.keys() | dense.keys()
    }


def bangla_ratio(text: str) -> float:
    """Return the fraction of Unicode letters that use the Bengali script."""
    letters = [char for char in text if unicodedata.category(char).startswith("L")]
    if not letters:
        return 0.0
    return sum("\u0980" <= char <= "\u09ff" for char in letters) / len(letters)


def _configured_alpha(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return min(1.0, max(0.0, value))


def alpha_for(text: str) -> float:
    """Choose the configured dense weight, favoring dense scores for Bangla."""
    if bangla_ratio(text) >= 0.5:
        return _configured_alpha("SEARCH_FUSION_ALPHA_BANGLA", 0.85)
    return _configured_alpha("SEARCH_FUSION_ALPHA", 0.95)
