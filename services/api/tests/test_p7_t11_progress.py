import logging
from unittest.mock import patch

import pytest
from django.core.management import call_command

from domains.issues.models import Issue, IssueStatus
from domains.search.embeddings import VECTOR_DIMENSION
from domains.search.management.commands.backfill_embeddings import Command as BackfillCommand
from domains.search.models import EmbeddingJob
from domains.search.progress import ProgressReporter

pytestmark = pytest.mark.django_db


def test_progress_logs_counts_without_sensitive_description(caplog, tmp_path):
    caplog.set_level(logging.INFO, logger="datasoft.progress")
    log_file = tmp_path / "progress.log"
    reporter = ProgressReporter("embedding", total=2, every=1, log_file=log_file)
    reporter.start()
    reporter.item(1)
    reporter.item(2)
    reporter.finish()
    messages = [record.getMessage() for record in caplog.records]
    assert any("embedding 1/2" in message for message in messages)
    assert any("embedding 2/2" in message for message in messages)
    assert any("elapsed" in message for message in messages)
    assert all("private request body" not in message for message in messages)
    assert log_file.read_text(encoding="utf-8").splitlines() == messages


def test_progress_every_must_be_positive():
    try:
        ProgressReporter("phase", total=0, every=0)
    except ValueError as exc:
        assert "positive" in str(exc)
    else:
        raise AssertionError("zero progress interval should be rejected")


def _pending_issue(officer):
    return Issue.objects.create(
        organization=officer.account.organization,
        created_by=officer,
        submitted_by=officer,
        status=IssueStatus.SUBMITTED,
        title="Synthetic embedding progress",
        description="Synthetic request text for a fixture only.",
    )


def test_backfill_warns_with_recovery_action_when_embedder_is_unavailable(officer_a, caplog):
    _pending_issue(officer_a)
    with patch(
        "domains.search.management.commands.backfill_embeddings._ml_embeddings", return_value=[]
    ):
        call_command("backfill_embeddings", progress_every=1)
    assert "Embedding unavailable" in caplog.text
    assert "ML_SERVICE_URL" in caplog.text
    assert "Synthetic request text" not in caplog.text


def test_seed_local_backfill_uses_injected_local_embedder(officer_a):
    _pending_issue(officer_a)

    class Encoded:
        def tolist(self):
            return [[1.0] + [0.0] * (VECTOR_DIMENSION - 1)]

    class FakeEmbedder:
        def encode(self, texts, normalize_embeddings):
            assert normalize_embeddings is True
            assert len(texts) == 1
            return Encoded()

    with patch.object(BackfillCommand, "_local_embedder", return_value=FakeEmbedder()):
        call_command("backfill_embeddings", embed_locally=True, progress_every=1)
    issue = Issue.objects.get(title="Synthetic embedding progress")
    assert issue.embedding is not None
    assert not EmbeddingJob.objects.filter(issue=issue, status="pending").exists()
