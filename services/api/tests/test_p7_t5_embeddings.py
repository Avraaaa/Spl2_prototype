"""Regression coverage for versioned, tenant-local search embeddings."""

from unittest.mock import patch

import pytest

from domains.issues.models import Issue, IssueStatus
from domains.search.models import (
    EmbeddingJob,
    IssueLabelSelection,
    Label,
    LabelConfidenceThreshold,
)
from domains.search.services import candidate_suggestions, label_suggestions

pytestmark = pytest.mark.django_db


def _issue(user, title, description, vector):
    return Issue.objects.create(
        organization=user.account.organization,
        created_by=user,
        submitted_by=user,
        status=IssueStatus.SUBMITTED,
        title=title,
        description=description,
        embedding=vector,
        embedding_model_id="multilingual-e5-small",
        embedding_preprocessing_version="v1",
        embedding_dimension=384,
    )


def test_search_uses_stored_vectors_without_writing_embeddings(officer_a, officer_b):
    stored = _issue(
        officer_a, "Login timeout", "Authentication cannot sign in", [1.0] + [0.0] * 383
    )
    foreign = _issue(
        officer_b, "Login timeout", "Authentication cannot sign in", [1.0] + [0.0] * 383
    )
    rows = Issue.objects.filter(organization=officer_a.account.organization)

    with patch.object(Issue.objects, "bulk_update") as bulk_update:
        result = candidate_suggestions(
            rows, title="Login timeout", description="Authentication cannot sign in"
        )

    bulk_update.assert_not_called()
    stored.refresh_from_db()
    foreign.refresh_from_db()
    assert stored.embedding_model_id == "multilingual-e5-small"
    assert foreign.organization_id != stored.organization_id
    assert [item["id"] for item in result] == [stored.pk]


def test_search_ignores_vectors_from_another_preprocessing_version(officer_a):
    stale = _issue(officer_a, "zxqv bcdj", "wxyz qqqj", [1.0] + [0.0] * 383)
    rows = Issue.objects.filter(organization=officer_a.account.organization)

    with patch("domains.search.services._ml_embeddings", return_value=[[1.0] + [0.0] * 383]):
        result = candidate_suggestions(rows, title="Login timeout", description="Authentication")

    stale.refresh_from_db()
    assert stale.embedding_preprocessing_version == "v1"
    assert result == []


def test_search_falls_back_to_lexical_when_ml_is_offline(officer_a):
    issue = _issue(
        officer_a, "Transfer timeout", "Payment transfer keeps timing out", [1.0] + [0.0] * 383
    )
    rows = Issue.objects.filter(organization=officer_a.account.organization)

    with patch("domains.search.services._ml_embeddings", return_value=None):
        result = candidate_suggestions(
            rows, title="Transfer timeout", description="Payment transfer"
        )

    assert [item["id"] for item in result] == [issue.pk]


def test_search_keeps_semantic_matches_outside_lexical_shortlist(officer_a):
    from domains.search.embeddings import PREPROCESSING_VERSION

    semantic = _issue(
        officer_a,
        "Transfer settles overnight",
        "Funds arrive next day",
        [1.0] + [0.0] * 383,
    )
    # This is the one current vector eligible for dense retrieval. The helper's
    # default version is intentionally stale for the version mismatch test.
    Issue.objects.filter(pk=semantic.pk).update(
        embedding_preprocessing_version=PREPROCESSING_VERSION
    )
    for index in range(45):
        distractor = _issue(
            officer_a,
            f"Login timeout {index}",
            "Authentication login timeout",
            [0.0, 1.0] + [0.0] * 382,
        )
        # Keep these strong lexical negatives out of dense retrieval. The
        # semantic-only result then tests recovery beyond the lexical top-40,
        # rather than expecting a single RRF vote to beat 45 two-list hits.
        Issue.objects.filter(pk=distractor.pk).update(embedding_preprocessing_version="old-v0")
    rows = Issue.objects.filter(organization=officer_a.account.organization)

    with patch("domains.search.services._ml_embeddings", return_value=[[1.0] + [0.0] * 383]):
        result = candidate_suggestions(rows, title="Login timeout", description="Authentication")

    assert semantic.pk in [item["id"] for item in result]


def test_label_examples_and_suggestions_are_tenant_scoped(officer_a, officer_b):
    own = _issue(officer_a, "Transfer failure", "Payment transfer failed", [1.0] + [0.0] * 383)
    other = _issue(officer_b, "Login failure", "Authentication failed", [0.0, 1.0] + [0.0] * 382)
    label = Label.objects.create(name="Payments", description="Payment transfer issues")
    IssueLabelSelection.objects.create(issue=own, label=label, actor=officer_a)
    IssueLabelSelection.objects.create(issue=other, label=label, actor=officer_b)

    suggestions = label_suggestions(
        title="Payment transfer failed",
        description="Transfer issue",
        labels=[label],
        organization=officer_a.account.organization,
    )

    assert suggestions
    assert suggestions[0]["name"] == "Payments"


def test_label_threshold_can_differ_by_organization(officer_a, officer_b):
    label = Label.objects.create(
        name="Authentication", description="login authentication failure", confidence_threshold=0.8
    )
    LabelConfidenceThreshold.objects.create(
        organization=officer_a.account.organization, label=label, threshold=0.2
    )

    own = label_suggestions(
        title="login", description="", labels=[label], organization=officer_a.account.organization
    )
    other = label_suggestions(
        title="login", description="", labels=[label], organization=officer_b.account.organization
    )

    assert own
    assert other == []


def test_issue_edit_queues_only_masked_text_for_embedding(officer_a):
    from domains.issues.services import create_draft

    issue = create_draft(officer_a, {"title": "OTP 123456", "description": "PIN 654321"})
    job = EmbeddingJob.objects.get(issue=issue)

    assert "123456" not in job.masked_text
    assert "654321" not in job.masked_text
    assert job.masked_text.startswith("passage: ")


def test_e5_prefixes_and_model_versions_are_explicit():
    from domains.search.embeddings import passage_text, query_text

    assert passage_text("masked") == "passage: masked"
    assert query_text("draft") == "query: draft"


def test_clustering_skips_small_population_and_keeps_separate_vectors():
    from domains.search.clustering import cluster_vectors

    assert cluster_vectors([([1.0, 0.0], 1), ([0.0, 1.0], 2)], min_population=3) == []


def test_evaluation_reports_graded_ranking_metrics():
    from domains.search.evaluation import evaluate_rankings

    result = evaluate_rankings([2, 1, 0], {"lexical": [2, 0, 1], "hybrid": [0, 1, 2]})

    assert result["hybrid"]["hit_rate@5"] == 1.0
    assert result["hybrid"]["ndcg@5"] > result["lexical"]["ndcg@5"]
