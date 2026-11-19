"""Masked, local-first suggestion services with deterministic keyword fallback."""

import re
from collections.abc import Iterable
from datetime import timedelta
from typing import cast

from django.db.models import QuerySet
from django.utils import timezone

from domains.issues.models import Issue, IssueStatus
from domains.issues.services import mask_sensitive

from .models import Label, TopicProposal

TOKEN = re.compile(r"[\w\u0980-\u09ff]{2,}", re.UNICODE)


def _tokens(value: str) -> set[str]:
    return {token.casefold() for token in TOKEN.findall(mask_sensitive(value))}


def _score(query_tokens: set[str], candidate_tokens: set[str]) -> float:
    if not query_tokens or not candidate_tokens:
        return 0.0
    overlap = len(query_tokens & candidate_tokens)
    return overlap / len(query_tokens | candidate_tokens)


def candidate_suggestions(rows: QuerySet[Issue], *, title: str, description: str) -> list[dict]:
    """Return at most five deterministic, tenant-scoped suggestions.

    A provisioned embedding model can be layered in later; this fallback keeps
    requests working offline and never sends unmasked text outside Django.
    """
    query_tokens = _tokens(f"{title} {description}")
    scored: list[tuple[float, Issue]] = []
    visible_statuses = [value for value in IssueStatus.values if value != IssueStatus.DRAFT]
    for issue in rows.filter(status__in=visible_statuses).iterator(chunk_size=2000):
        score = _score(query_tokens, _tokens(f"{issue.title} {issue.description}"))
        if score > 0:
            scored.append((score, issue))
    scored.sort(key=lambda item: (-item[0], -item[1].pk))
    return [
        {
            "id": issue.pk,
            "reference": issue.reference,
            "title": issue.title,
            "status": issue.status,
            "score": round(score, 4),
        }
        for score, issue in scored[:5]
    ]


def label_suggestions(*, title: str, description: str, labels: Iterable[Label]) -> list[dict]:
    tokens = _tokens(f"{title} {description}")
    suggestions: list[dict[str, object]] = []
    for label in labels:
        keywords = {str(value).casefold() for value in label.keywords if isinstance(value, str)}
        score = _score(tokens, keywords)
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
    for issue in rows.filter(created_at__gte=cutoff).iterator(chunk_size=2000):
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
