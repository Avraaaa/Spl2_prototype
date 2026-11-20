"""Masked, local-first hybrid suggestions with a deterministic fallback."""

import json
import os
import re
from collections.abc import Iterable
from datetime import timedelta
from typing import cast
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.db.models import QuerySet
from django.utils import timezone
from pgvector.django import CosineDistance

from domains.issues.models import Issue, IssueStatus
from domains.issues.services import mask_sensitive

from .models import IssueLabelSelection, Label, TopicProposal

TOKEN = re.compile(r"[\w\u0980-\u09ff]{2,}", re.UNICODE)


def _tokens(value: str) -> set[str]:
    return {token.casefold() for token in TOKEN.findall(mask_sensitive(value))}


def _score(query_tokens: set[str], candidate_tokens: set[str]) -> float:
    if not query_tokens or not candidate_tokens:
        return 0.0
    overlap = len(query_tokens & candidate_tokens)
    return overlap / len(query_tokens | candidate_tokens)


def _ml_embeddings(texts: list[str]) -> list[list[float]] | None:
    base = os.getenv("ML_SERVICE_URL", "").rstrip("/")
    token = os.getenv("ML_SHARED_TOKEN", "")
    if not base or not token:
        return None
    request = Request(
        f"{base}/internal/embed",
        data=json.dumps({"texts": texts}).encode(),
        headers={"Content-Type": "application/json", "X-Service-Token": token},
        method="POST",
    )
    try:
        with urlopen(request, timeout=1.5) as response:
            body = json.loads(response.read().decode())
        vectors = body.get("vectors")
        if not isinstance(vectors, list) or len(vectors) != len(texts):
            return None
        if any(not isinstance(vector, list) or len(vector) != 384 for vector in vectors):
            return None
        return [[float(value) for value in vector] for vector in vectors]
    except (OSError, URLError, ValueError, TypeError, KeyError):
        return None


def _rrf(ranks: list[dict[int, int]], *, k: int = 60) -> dict[int, float]:
    fused: dict[int, float] = {}
    for ranking in ranks:
        for issue_id, rank in ranking.items():
            fused[issue_id] = fused.get(issue_id, 0.0) + (1 / (k + rank))
    return fused


def candidate_suggestions(
    rows: QuerySet[Issue],
    *,
    title: str,
    description: str,
    product: int | None = None,
    module: int | None = None,
) -> list[dict]:
    """Return at most five tenant-scoped hybrid suggestions.

    Django narrows the authorized candidate set first. A local model and pgvector
    add semantic ranking when configured; lexical ranking remains the safe fallback.
    """
    cutoff = timezone.now() - timedelta(days=365)
    scoped = rows.filter(
        status__in=[value for value in IssueStatus.values if value != IssueStatus.DRAFT],
        created_at__gte=cutoff,
    )
    if product is not None:
        scoped = scoped.filter(product_id=product)
    if module is not None:
        scoped = scoped.filter(module_id=module)
    candidates = list(scoped[:2000])
    query_tokens = _tokens(f"{title} {description}")
    lexical: list[tuple[float, Issue]] = []
    for issue in candidates:
        score = _score(query_tokens, _tokens(f"{issue.title} {issue.description}"))
        if score > 0:
            lexical.append((score, issue))
    lexical.sort(key=lambda item: (-item[0], -item[1].pk))
    lexical_rank = {issue.pk: rank for rank, (_, issue) in enumerate(lexical, start=1)}

    semantic_rank: dict[int, int] = {}
    vectors = _ml_embeddings(
        [f"{mask_sensitive(title)} {mask_sensitive(description)}"]
        + [f"{mask_sensitive(issue.title)} {mask_sensitive(issue.description)}" for issue in candidates]
    )
    if vectors:
        query_vector, candidate_vectors = vectors[0], vectors[1:]
        for issue, vector in zip(candidates, candidate_vectors, strict=True):
            issue.embedding = vector
        Issue.objects.bulk_update(candidates, ["embedding"], batch_size=200)
        try:
            semantic_rows = (
                scoped.filter(embedding__isnull=False)
                .annotate(distance=CosineDistance("embedding", query_vector))
                .order_by("distance", "-id")[:50]
            )
            semantic_rank = {
                issue.pk: rank for rank, issue in enumerate(semantic_rows, start=1)
            }
        except Exception:
            semantic_rank = {}

    fused = _rrf([ranking for ranking in (lexical_rank, semantic_rank) if ranking])
    ranked = sorted(
        (issue for issue in candidates if issue.pk in fused),
        key=lambda issue: (-fused[issue.pk], -issue.pk),
    )
    return [
        {
            "id": issue.pk,
            "reference": issue.reference,
            "title": issue.title,
            "status": issue.status,
            "score": round(fused[issue.pk], 4),
        }
        for issue in ranked[:5]
    ]


def label_suggestions(
    *, title: str, description: str, labels: Iterable[Label], organization=None
) -> list[dict]:
    tokens = _tokens(f"{title} {description}")
    suggestions: list[dict[str, object]] = []
    for label in labels:
        label_tokens = _tokens(label.description)
        label_tokens.update(
            str(value).casefold() for value in label.keywords if isinstance(value, str)
        )
        score = _score(tokens, label_tokens)
        selections = IssueLabelSelection.objects.filter(label=label).select_related("issue")
        if organization is not None:
            selections = selections.filter(issue__organization=organization)
        for selection in selections[:25]:
            score = max(
                score,
                _score(tokens, _tokens(f"{selection.issue.title} {selection.issue.description}")),
            )
        if score >= label.confidence_threshold:
            suggestions.append({"id": label.pk, "name": label.name, "score": round(score, 4)})
    return sorted(
        suggestions,
        key=lambda item: (-cast(float, item["score"]), cast(int, item["id"])),
    )[:5]


def cluster_recent_unidentified(rows: QuerySet[Issue], *, days: int = 90) -> list[dict]:
    """Group recent masked issues by a shared keyword for admin review."""
    cutoff = timezone.now() - timedelta(days=max(1, days))
    token_rows: list[tuple[Issue, set[str]]] = []
    frequencies: dict[str, int] = {}
    for issue in rows.filter(
        created_at__gte=cutoff,
        status__in=[value for value in IssueStatus.values if value != IssueStatus.DRAFT],
        label_selection__isnull=True,
    ).iterator(chunk_size=2000):
        tokens = _tokens(f"{issue.title} {issue.description}")
        if not tokens:
            continue
        token_rows.append((issue, tokens))
        for token in tokens:
            frequencies[token] = frequencies.get(token, 0) + 1
    groups: dict[str, list[Issue]] = {}
    for issue, tokens in token_rows:
        keyword = max(tokens, key=lambda token: (frequencies[token], token))
        groups.setdefault(keyword, []).append(issue)
    return [
        {
            "title": keyword.title(),
            "keywords": [keyword],
            "issue_ids": [issue.pk for issue in issues],
        }
        for keyword, issues in sorted(groups.items())
        if len(issues) >= 2
    ]


def create_topic_proposals(
    *, organization, rows: QuerySet[Issue], days: int = 90
) -> list[TopicProposal]:
    return [
        TopicProposal.objects.create(organization=organization, **group)
        for group in cluster_recent_unidentified(rows, days=days)
    ]


def precision_at_k(expected: set[int], predicted: list[int], k: int = 5) -> float:
    selected = predicted[: max(1, k)]
    return sum(item in expected for item in selected) / len(selected)


def recall_at_k(expected: set[int], predicted: list[int], k: int = 5) -> float:
    if not expected:
        return 0.0
    return sum(item in expected for item in predicted[: max(1, k)]) / len(expected)
