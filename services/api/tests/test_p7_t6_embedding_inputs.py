"""Regression coverage for compatible normalized embedding inputs."""

import pytest

from domains.search.embeddings import embedding_input, passage_text, query_text


@pytest.mark.django_db
def test_e5_prefix_helpers_remain_explicit_and_normalization_is_supplemental():
    assert passage_text("masked") == "passage: masked"
    assert query_text("draft") == "query: draft"
    prepared = embedding_input("passage: masked ashche")
    assert prepared.startswith("passage: masked ashche\nSupplemental normalized text: ")
    assert "OTP" in embedding_input("passage: OTP E105 RTGS BEFTN NPSB LoginModule ashche")
