import json
from pathlib import Path

import pytest

from domains.issues.models import Issue, IssueStatus
from domains.search.evaluation import _lexical_tokens, lexical_hit_rate_at_5
from domains.search.models import Label
from domains.search.services import _tokens

from .conftest import client_for

pytestmark = pytest.mark.django_db


def test_synthetic_fixture_ranks_bangla_and_mixed_cases_with_keyword_fallback():
    fixture_path = Path(__file__).resolve().parents[3] / "seed" / "search_evaluation.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    bangla_case = next(row for row in fixture["queries"] if row["language"] == "Bangla")
    mixed_case = next(row for row in fixture["queries"] if row["language"] == "Code-switched")

    assert "যায়" in _lexical_tokens(bangla_case["text"], normalize=False)
    assert lexical_hit_rate_at_5({"queries": [bangla_case, mixed_case]}, normalize=False) == 1.0


def _issue(user, title, description):
    return Issue.objects.create(
        organization=user.account.organization,
        created_by=user,
        submitted_by=user,
        status=IssueStatus.SUBMITTED,
        title=title,
        description=description,
    )


def test_bangla_lexical_tokens_keep_vowel_marks_and_rank_similar_request(officer_a):
    similar = _issue(
        officer_a,
        "টাকা ট্রান্সফার আটকে যায়",
        "নিশ্চিত করার পর লেনদেন আটকে থাকে",
    )
    unrelated = _issue(
        officer_a,
        "লেনদেনের ফি ভুল দেখায়",
        "ট্রান্সফার স্ক্রিনে অতিরিক্ত চার্জ দেখা যায়",
    )

    tokens = _tokens("টাকা ট্রান্সফার আটকে যায়")
    response = client_for(officer_a).post(
        "/api/search/suggestions/",
        {"title": "টাকা ট্রান্সফার আটকে যায়", "description": "নিশ্চিত করার পর লেনদেন আটকে থাকে"},
        format="json",
    )

    assert {"টাকা", "ট্রান্সফার", "আটকে", "যায়"} <= tokens
    assert response.status_code == 200
    result_ids = [row["id"] for row in response.json()["duplicates"]]
    assert result_ids.index(similar.pk) < result_ids.index(unrelated.pk)


def test_bangla_and_mixed_text_suggest_matching_labels(officer_a):
    Label.objects.create(
        name="Transaction",
        description="লেনদেন ট্রান্সফার টাকা পাঠানো",
        keywords=["লেনদেন", "transfer", "ট্রান্সফার"],
        confidence_threshold=0.2,
    )
    Label.objects.create(
        name="User Interface",
        description="স্ক্রিন বোতাম প্রদর্শন",
        keywords=["স্ক্রিন", "button"],
        confidence_threshold=0.2,
    )

    response = client_for(officer_a).post(
        "/api/search/suggestions/",
        {"title": "লেনদেন transfer আটকে যায়", "description": "টাকা পাঠানোর পর ট্রান্সফার আটকে থাকে"},
        format="json",
    )

    assert response.status_code == 200
    names = [row["name"] for row in response.json()["labels"]]
    assert "Transaction" in names
    assert "User Interface" not in names
