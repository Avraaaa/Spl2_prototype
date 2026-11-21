"""Ranking metrics shared by the reproducible synthetic evaluation command."""

import re
from math import log2
from pathlib import Path

from .banglish import normalize_banglish


def hit_rate_at_k(grades: list[int], ranking: list[int], k: int = 5) -> float:
    return float(any(grades[index] > 0 for index in ranking[:k]))


def recall_at_k(grades: list[int], ranking: list[int], k: int = 5) -> float:
    relevant = sum(grade > 0 for grade in grades)
    return sum(grades[index] > 0 for index in ranking[:k]) / relevant if relevant else 0.0


def ndcg_at_k(grades: list[int], ranking: list[int], k: int = 5) -> float:
    dcg = sum(
        (2 ** grades[index] - 1) / log2(position + 2) for position, index in enumerate(ranking[:k])
    )
    ideal = sorted(grades, reverse=True)[:k]
    idcg = sum((2**grade - 1) / log2(position + 2) for position, grade in enumerate(ideal))
    return dcg / idcg if idcg else 0.0


def reciprocal_rank(grades: list[int], ranking: list[int], k: int = 5) -> float:
    return next(
        (1 / (position + 1) for position, index in enumerate(ranking[:k]) if grades[index] > 0), 0.0
    )


def evaluate_rankings(
    grades: list[int], rankings: dict[str, list[int]]
) -> dict[str, dict[str, float]]:
    metrics = ("hit_rate@5", "recall@5", "ndcg@5", "mrr@5")
    result = {}
    for name, ranking in rankings.items():
        values = (
            hit_rate_at_k(grades, ranking),
            recall_at_k(grades, ranking),
            ndcg_at_k(grades, ranking),
            reciprocal_rank(grades, ranking),
        )
        result[name] = {
            metric: round(value, 4) for metric, value in zip(metrics, values, strict=True)
        }
    return result


_TOKEN = re.compile(r"[\w\u0980-\u09ff]+", re.UNICODE)


def _lexical_tokens(value: str, normalize: bool) -> set[str]:
    text = normalize_banglish(value) if normalize else value
    return {token.casefold() for token in _TOKEN.findall(text)}


def lexical_hit_rate_at_5(fixture: dict, *, normalize: bool) -> float:
    queries = fixture.get("queries", [])
    if not queries:
        return 0.0
    hits = 0.0
    for sample in queries:
        query_tokens = _lexical_tokens(sample["text"], normalize)
        candidates = sample["candidates"]
        ranked = sorted(
            range(len(candidates)),
            key=lambda index: (
                -len(query_tokens & _lexical_tokens(candidates[index]["text"], normalize)),
                index,
            ),
        )
        hits += hit_rate_at_k([item["grade"] for item in candidates], ranked)
    return hits / len(queries)


def model_matrix(
    *,
    model_ids: list[str],
    models_dir: Path,
    embedder_factory,
    configurations: list[dict] | None = None,
) -> tuple[list[dict], list[str]]:
    """Build configured evaluation runs, skipping absent optional local models."""
    runs = configurations or [
        {"name": "lexical", "mode": "lexical"},
        {"name": "dense", "mode": "dense"},
        {"name": "hybrid", "mode": "hybrid"},
        {"name": "hybrid+normalization", "mode": "hybrid", "normalize": True},
    ]
    results = [dict(run) for run in runs]
    skipped = []
    for model_id in model_ids:
        checkpoint = models_dir / model_id
        if not checkpoint.is_dir():
            skipped.append(f"{model_id}: missing local checkpoint")
            continue
        results.append(
            {
                "name": model_id,
                "mode": "hybrid",
                "model_id": model_id,
                "embedder": embedder_factory(checkpoint, model_id),
            }
        )
    return results, skipped


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * fraction + 0.9999)))
    return round(ordered[index], 3)
