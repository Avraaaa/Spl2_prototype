"""Deterministic average-linkage cosine clustering for tenant-local vectors."""

from math import sqrt


def _cosine_distance(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = sqrt(sum(value * value for value in left))
    right_norm = sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 1.0
    return max(0.0, min(2.0, 1.0 - dot / (left_norm * right_norm)))


def cluster_vectors(
    items: list[tuple[list[float], int]], *, cutoff: float = 0.3, min_population: int = 20
) -> list[list[int]]:
    """Return IDs from clusters of at least three, or none below population threshold."""
    if len(items) < min_population or not 0 <= cutoff <= 2:
        return []
    clusters = [[index] for index in range(len(items))]
    while True:
        best: tuple[float, int, int] | None = None
        for left_index, left in enumerate(clusters):
            for right_index in range(left_index + 1, len(clusters)):
                right = clusters[right_index]
                distance = sum(
                    _cosine_distance(items[a][0], items[b][0]) for a in left for b in right
                ) / (len(left) * len(right))
                candidate = (distance, left_index, right_index)
                if best is None or candidate < best:
                    best = candidate
        if best is None or best[0] > cutoff:
            break
        _, left_index, right_index = best
        clusters[left_index].extend(clusters.pop(right_index))
    return [[items[index][1] for index in cluster] for cluster in clusters if len(cluster) >= 3]
