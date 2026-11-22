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


def validate_fixture(fixture: dict) -> dict:
    """Validate minimum evaluation breadth and return reproducible variant counts."""
    queries = fixture.get("queries", [])
    counts: dict[str, int] = {}
    incidents: set[str] = set()
    for sample in queries:
        variant = sample.get("language")
        incident = sample.get("incident")
        if not variant or not incident or not sample.get("candidates"):
            raise ValueError("Every evaluation query needs a language, incident, and candidates")
        text = sample.get("text", "")
        compact = "".join(character for character in text if not character.isspace())
        if not text.strip() or re.search(r"\\u[0-9a-fA-F]{4}", text):
            raise ValueError("Evaluation query text must contain decoded Unicode text")
        if compact.count("?") / max(1, len(compact)) > 0.5:
            raise ValueError("Evaluation query text cannot be mostly question marks")
        if not sample.get("expected_label") or not sample.get("topic_id"):
            raise ValueError("Every evaluation query needs expected_label and topic_id")
        counts[variant] = counts.get(variant, 0) + 1
        incidents.add(incident)
        if any(item.get("grade") not in (0, 1, 2) for item in sample["candidates"]):
            raise ValueError("Candidate grades must be 0, 1, or 2")
    required = {"English", "Bangla", "Banglish", "Code-switched", "Typo"}
    if (
        len(queries) < 60
        or not required.issubset(counts)
        or any(counts.get(variant, 0) < 10 for variant in required)
    ):
        raise ValueError("Evaluation fixture needs at least 10 queries in each of five variants")
    if fixture.get("split_by") != "incident" or not fixture.get("augmentation_applied_after_split"):
        raise ValueError("Evaluation fixture must split by incident before augmentation")
    return {"query_count": len(queries), "incident_count": len(incidents), "variant_counts": counts}


def require_local_embedder(
    configurations: list[dict], embedder: object | None
) -> tuple[list[dict], list[dict]]:
    """Keep lexical runs and mark embedding runs skipped unless a local model loaded."""
    if embedder is not None:
        return [
            {**run, "embedder": embedder} if run.get("mode") in {"dense", "hybrid"} else run
            for run in configurations
        ], []
    kept = [run for run in configurations if run.get("mode") == "lexical"]
    skipped = [
        {
            "name": run["name"],
            "status": "SKIPPED",
            "reason": "no local embedder available",
        }
        for run in configurations
        if run.get("mode") in {"dense", "hybrid"}
    ]
    return kept, skipped


def label_metrics(rows: list[dict]) -> dict:
    """Score top-1 label decisions, coverage and abstention on synthetic cases."""
    if not rows:
        return {
            "accuracy@1": 0.0,
            "coverage": 0.0,
            "abstention_rate": 0.0,
            "sample_count": 0,
            "per_tenant": {},
        }

    def measure(samples: list[dict]) -> dict[str, object]:
        covered = [
            row
            for row in samples
            if row.get("predicted") not in (None, "")
            and row.get("score", 1.0) >= row.get("threshold", 0.0)
        ]
        return {
            "accuracy@1": round(
                sum(row.get("predicted") == row.get("expected") for row in covered) / len(samples),
                4,
            ),
            "coverage": round(len(covered) / len(samples), 4),
            "abstention_rate": round((len(samples) - len(covered)) / len(samples), 4),
            "sample_count": len(samples),
        }

    result: dict[str, object] = measure(rows)
    tenants = sorted({row.get("tenant", "default") for row in rows})
    result["per_tenant"] = {
        tenant: measure([row for row in rows if row.get("tenant", "default") == tenant])
        for tenant in tenants
    }
    return result


def topic_cluster_purity(clusters: list[list[str]], topic_ids: dict[str, str]) -> float:
    """Micro-average dominant ground-truth topic share over clustered items."""
    clustered = [item for cluster in clusters for item in cluster if item in topic_ids]
    if not clustered:
        return 0.0
    from collections import Counter

    correct = sum(
        max(Counter(topic_ids[item] for item in cluster if item in topic_ids).values(), default=0)
        for cluster in clusters
    )
    return round(correct / len(clustered), 4)


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * fraction + 0.9999)))
    return round(ordered[index], 3)
