"""P9-T1 score fusion and held-out split checks."""

import hashlib

import pytest

from domains.search.fusion import (
    alpha_for,
    bangla_ratio,
    fuse,
    normalise_dense,
    normalise_lexical,
)
from domains.search.management.commands.compare_features import Command


def test_score_normalisation_handles_empty_equal_and_negative_values():
    assert normalise_lexical([]) == []
    assert normalise_lexical([4.0, 4.0]) == [0.0, 0.0]
    assert normalise_lexical([-2.0, 0.0, 2.0]) == [0.0, 0.5, 1.0]
    assert normalise_dense([-2.0, -1.0, 0.0, 1.0, 2.0]) == [0.0, 0.0, 0.5, 1.0, 1.0]


def test_convex_fusion_endpoints_and_missing_candidates():
    lexical = {1: 1.0, 2: 0.0}
    dense = {2: 1.0, 3: 0.5}
    assert fuse(lexical, dense, 1.0) == {1: 0.0, 2: 1.0, 3: 0.5}
    assert fuse(lexical, dense, 0.0) == lexical | {3: 0.0}
    assert fuse(lexical, dense, 0.5) == {1: 0.5, 2: 0.5, 3: 0.25}


def test_bangla_ratio_and_alpha_environment_overrides(monkeypatch):
    assert bangla_ratio("abc বাংলা") == 0.4
    assert bangla_ratio("বাংলা বাংলা") == 1.0
    monkeypatch.setenv("SEARCH_FUSION_ALPHA", "0.7")
    monkeypatch.setenv("SEARCH_FUSION_ALPHA_BANGLA", "1.2")
    assert alpha_for("english") == 0.7
    assert alpha_for("বাংলা") == 1.0
    monkeypatch.setenv("SEARCH_FUSION_ALPHA", "invalid")
    assert alpha_for("english") == 0.95


def test_evaluation_split_is_stable_by_issue_key():
    key = "synthetic-issue-42"
    expected = int(hashlib.sha256(key.encode("utf-8")).hexdigest(), 16) % 2
    assert Command._evaluation_split(key) == ("tune" if expected == 0 else "holdout")
    assert Command._evaluation_split(key) == Command._evaluation_split(key)


def test_alpha_sweep_reports_metrics_for_both_halves():
    keys = {}
    for index in range(100):
        key = f"synthetic-{index}"
        keys.setdefault(Command._evaluation_split(key), key)
        if len(keys) == 2:
            break
    samples = [
        {
            "key": key,
            "text": "settlement timeout",
            "grades": [2, 0],
            "lexical": {0: 1.0, 1: 0.0},
            "dense": {0: 0.0, 1: 1.0},
            "ids": [0, 1],
            "candidate_ids": [100, 200],
            "hard_negative_ids": {200},
        }
        for key in keys.values()
    ]

    report = Command._alpha_sweep(samples, [0.0, 1.0])

    assert set(report["default"]["alpha_results"]) == {"0.0", "1.0"}
    assert report["default"]["tune"]["sample_count"] == 1
    assert report["default"]["holdout"]["sample_count"] == 1
    assert "hard_negative_fp@5" in report["default"]["holdout"]


@pytest.mark.django_db
def test_candidate_fusion_keeps_authorized_queryset_and_lexical_fallback(
    officer_a, officer_b, monkeypatch
):
    from domains.issues.models import Issue, IssueStatus
    from domains.search import services

    own = Issue.objects.create(
        organization=officer_a.account.organization,
        created_by=officer_a,
        submitted_by=officer_a,
        status=IssueStatus.SUBMITTED,
        title="Synthetic settlement timeout",
        description="Settlement returns timeout after submit",
    )
    Issue.objects.create(
        organization=officer_b.account.organization,
        created_by=officer_b,
        submitted_by=officer_b,
        status=IssueStatus.SUBMITTED,
        title="Synthetic settlement timeout",
        description="Settlement returns timeout after submit",
    )
    monkeypatch.setattr(services, "_ml_embeddings", lambda _texts: None)

    suggestions = services.candidate_suggestions(
        Issue.objects.filter(organization=officer_a.account.organization),
        title="Synthetic settlement timeout",
        description="Settlement returns timeout after submit",
    )

    assert [item["id"] for item in suggestions] == [own.pk]
    assert suggestions[0]["score"] >= 0
