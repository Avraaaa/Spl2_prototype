"""Masked, local-first hybrid suggestions with a deterministic fallback."""

import json
import os
import re
from collections.abc import Iterable
from datetime import timedelta
from math import log
from typing import cast
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector, TrigramSimilarity
from django.db.models import QuerySet
from django.db.models.functions import Greatest
from django.utils import timezone
from pgvector.django import CosineDistance

from domains.issues.models import Issue, IssueStatus
from domains.issues.services import mask_sensitive

from .clustering import cluster_vectors
from .embeddings import MODEL_ID, PREPROCESSING_VERSION, VECTOR_DIMENSION, query_text
from .models import IssueLabelSelection, Label, LabelConfidenceThreshold, TopicProposal

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
    query_value = mask_sensitive(f"{title} {description}")
    search_vector = SearchVector("title", "description", config="simple")
    search_query = SearchQuery(query_value, config="simple")
    scoped = scoped.annotate(
        _fts_rank=SearchRank(search_vector, search_query, cover_density=True),
        _trigram_rank=Greatest(
            TrigramSimilarity("title", query_value),
            TrigramSimilarity("description", query_value),
        ),
    )
    candidates = list(scoped.order_by("-_fts_rank", "-_trigram_rank", "-id")[:40])
    query_tokens = _tokens(f"{title} {description}")
    lexical: list[tuple[float, Issue]] = []
    for issue in candidates:
        score = max(
            float(issue._fts_rank) + float(issue._trigram_rank),
            _score(query_tokens, _tokens(f"{issue.title} {issue.description}")),
        )
        if score > 0:
            lexical.append((score, issue))
    lexical.sort(key=lambda item: (-item[0], -item[1].pk))
    lexical = lexical[:40]
    lexical_rank = {issue.pk: rank for rank, (_, issue) in enumerate(lexical, start=1)}

    semantic_rank: dict[int, int] = {}
    semantic_candidates: list[Issue] = []
    vectors = _ml_embeddings([query_text(f"{title}\n{description}")])
    if vectors:
        try:
            semantic_rows = list(
                scoped.filter(
                    embedding__isnull=False,
                    embedding_model_id=MODEL_ID,
                    embedding_preprocessing_version=PREPROCESSING_VERSION,
                    embedding_dimension=VECTOR_DIMENSION,
                )
                .annotate(distance=CosineDistance("embedding", vectors[0]))
                .order_by("distance", "-id")[:40]
            )
            semantic_candidates = [cast(Issue, issue) for issue in semantic_rows]
            semantic_rank = {issue.pk: rank for rank, issue in enumerate(semantic_rows, start=1)}
        except Exception:
            semantic_rank = {}

    fused = _rrf([ranking for ranking in (lexical_rank, semantic_rank) if ranking])
    candidate_by_id: dict[int, Issue] = {issue.pk: cast(Issue, issue) for issue in candidates}
    candidate_by_id.update({issue.pk: cast(Issue, issue) for issue in semantic_candidates})
    ranked = sorted(
        (issue for issue_id, issue in candidate_by_id.items() if issue_id in fused),
        key=lambda issue: (-fused[issue.pk], -issue.pk),
    )
    minimum = float(os.getenv("SEARCH_MIN_RELEVANCE", "0"))
    ranked = [issue for issue in ranked if fused[issue.pk] >= minimum]
    return [
        {
            "id": issue.pk,
            "reference": issue.reference,
            "title": issue.title,
            "status": issue.status,
            "score": round(fused[issue.pk], 4),
            "evidence": sorted(query_tokens & _tokens(f"{issue.title} {issue.description}"))[:8],
        }
        for issue in ranked[:5]
    ]


def label_suggestions(
    *, title: str, description: str, labels: Iterable[Label], organization=None
) -> list[dict]:
    tokens = _tokens(f"{title} {description}")
    suggestions: list[dict[str, object]] = []
    query_vectors = _ml_embeddings([query_text(f"{title}\n{description}")])
    query_vector = query_vectors[0] if query_vectors else None
    for label in labels:
        threshold = label.confidence_threshold
        if organization is not None:
            override = LabelConfidenceThreshold.objects.filter(
                organization=organization, label=label
            ).first()
            if override is not None:
                threshold = override.threshold
        label_tokens = _tokens(label.description)
        label_tokens.update(
            str(value).casefold() for value in label.keywords if isinstance(value, str)
        )
        score = _score(tokens, label_tokens)
        selections = IssueLabelSelection.objects.filter(label=label).select_related("issue")
        if organization is not None:
            selections = selections.filter(issue__organization=organization)
        examples: list[Issue] = []
        for selection in selections.select_related("issue")[:100]:
            if (
                query_vector is not None
                and selection.issue.embedding is not None
                and selection.issue.embedding_model_id == MODEL_ID
                and selection.issue.embedding_preprocessing_version == PREPROCESSING_VERSION
                and selection.issue.embedding_dimension == VECTOR_DIMENSION
            ):
                examples.append(selection.issue)
            score = max(
                score,
                _score(tokens, _tokens(f"{selection.issue.title} {selection.issue.description}")),
            )
        if examples and query_vector is not None:
            diverse: list[Issue] = []
            for issue in examples:
                issue_vector = cast(list[float], issue.embedding)
                if any(
                    sum(
                        a * b
                        for a, b in zip(
                            issue_vector, cast(list[float], prior.embedding), strict=True
                        )
                    )
                    >= 0.98
                    for prior in diverse
                ):
                    continue
                diverse.append(issue)
            neighbors = sorted(
                (
                    sum(
                        a * b
                        for a, b in zip(
                            query_vector, cast(list[float], issue.embedding), strict=True
                        )
                    )
                    for issue in diverse
                ),
                reverse=True,
            )[:25]
            if neighbors:
                positive = [max(0.0, similarity) for similarity in neighbors]
                denominator = sum(positive)
                if denominator:
                    score = max(score, sum(value * value for value in positive) / denominator)
        if score >= threshold:
            suggestions.append(
                {"id": label.pk, "name": label.name, "score": round(score, 4), "tentative": False}
            )
        elif not examples and query_vector is not None and label.description.strip():
            prototype = _ml_embeddings([f"passage: {mask_sensitive(label.description)}"])
            if prototype:
                dense_score = sum(a * b for a, b in zip(query_vector, prototype[0], strict=True))
                if dense_score >= max(0.65, threshold):
                    suggestions.append(
                        {
                            "id": label.pk,
                            "name": label.name,
                            "score": round(dense_score * 0.8, 4),
                            "tentative": True,
                        }
                    )
    return sorted(
        suggestions,
        key=lambda item: (-cast(float, item["score"]), cast(int, item["id"])),
    )[:5]


def cluster_recent_unidentified(rows: QuerySet[Issue], *, days: int = 90) -> list[dict]:
    """Cluster compatible recent vectors; use keyword fallback before backfill."""
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
    vector_rows = [
        (issue, list(issue.embedding))
        for issue, _ in token_rows
        if issue.embedding is not None
        and issue.embedding_model_id == MODEL_ID
        and issue.embedding_preprocessing_version == PREPROCESSING_VERSION
        and issue.embedding_dimension == VECTOR_DIMENSION
    ]
    if len(vector_rows) >= 20:
        clusters = cluster_vectors(
            [(vector, index) for index, (_, vector) in enumerate(vector_rows)],
            cutoff=float(os.getenv("TOPIC_DISTANCE_CUTOFF", "0.3")),
            min_population=20,
        )
        proposals = []
        for cluster in clusters:
            issues = [vector_rows[index][0] for index in cluster]
            terms = set().union(*(tokens for issue, tokens in token_rows if issue in issues))
            counts = {
                term: sum(term in _tokens(f"{issue.title} {issue.description}") for issue in issues)
                for term in terms
            }
            scores = {
                term: counts[term] * log(1 + len(token_rows) / max(1, frequencies.get(term, 0)))
                for term in terms
            }
            keywords = sorted(terms, key=lambda term: (-scores[term], term))[:5]
            proposals.append(
                {
                    "title": " ".join(word.title() for word in keywords[:3])[:160],
                    "keywords": keywords,
                    "issue_ids": [issue.pk for issue in issues],
                    "representatives": [
                        {
                            "issue_id": issue.pk,
                            "title": issue.title,
                            "snippet": issue.description[:240],
                        }
                        for issue in sorted(issues, key=lambda row: row.created_at, reverse=True)[
                            :3
                        ]
                    ],
                }
            )
        return proposals
    if vector_rows:
        return []

    groups: dict[str, list[Issue]] = {}
    for issue, tokens in token_rows:
        keyword = max(tokens, key=lambda token: (frequencies[token], token))
        groups.setdefault(keyword, []).append(issue)
    return [
        {
            "title": keyword.title(),
            "keywords": [keyword],
            "issue_ids": [issue.pk for issue in issues],
            "representatives": [
                {"issue_id": issue.pk, "title": issue.title, "snippet": issue.description[:240]}
                for issue in issues[:3]
            ],
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
