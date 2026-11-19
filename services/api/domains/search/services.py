"""Masked, local-first suggestion services with deterministic keyword fallback."""

import re
from collections.abc import Iterable
from typing import cast

from django.db.models import QuerySet

from domains.issues.models import Issue, IssueStatus
from domains.issues.services import mask_sensitive

from .models import Label

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
