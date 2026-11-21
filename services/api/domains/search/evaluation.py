"""Ranking metrics shared by the reproducible synthetic evaluation command."""

from math import log2


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
