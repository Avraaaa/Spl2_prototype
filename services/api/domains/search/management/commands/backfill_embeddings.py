"""Process pending local embedding jobs and backfill eligible requests."""

import os
from hashlib import sha256
from pathlib import Path

from django.core.management.base import BaseCommand

from domains.issues.models import Issue, IssueStatus
from domains.search.embeddings import (
    MODEL_ID,
    PREPROCESSING_VERSION,
    VECTOR_DIMENSION,
    embedding_input,
    passage_text,
)
from domains.search.models import EmbeddingJob
from domains.search.progress import ProgressReporter
from domains.search.services import _ml_embeddings


class Command(BaseCommand):
    help = "Backfill missing request embeddings using the configured local ML service."

    def add_arguments(self, parser):
        parser.add_argument("--progress-every", type=int, default=25)
        parser.add_argument("--log-file")
        parser.add_argument("--embed-locally", action="store_true")

    @staticmethod
    def _local_embedder():
        from sentence_transformers import SentenceTransformer

        model_dir = Path(os.getenv("ML_MODELS_DIR", "./models")) / MODEL_ID
        if not model_dir.is_dir():
            raise FileNotFoundError(f"local checkpoint not found at {model_dir}")
        return SentenceTransformer(str(model_dir), local_files_only=True)

    def handle(self, *args, **options):
        if options["progress_every"] < 1:
            raise ValueError("--progress-every must be positive")
        log_file = options["log_file"]
        missing = Issue.objects.exclude(status=IssueStatus.DRAFT).filter(embedding__isnull=True)
        reporter = ProgressReporter(
            "queueing missing embeddings", missing.count(), options["progress_every"], log_file
        )
        reporter.start()
        for done, issue in enumerate(missing.iterator(chunk_size=100), start=1):
            text = passage_text(f"{issue.title}\n{issue.description}")
            EmbeddingJob.objects.update_or_create(
                issue=issue,
                defaults={
                    "masked_text": text,
                    "content_hash": sha256(text.encode()).hexdigest(),
                    "status": "pending",
                },
            )
            reporter.item(done)
        reporter.finish()

        stale = Issue.objects.exclude(status=IssueStatus.DRAFT).exclude(
            embedding_model_id=MODEL_ID,
            embedding_preprocessing_version=PREPROCESSING_VERSION,
            embedding_dimension=VECTOR_DIMENSION,
        )
        reporter = ProgressReporter(
            "queueing stale embeddings", stale.count(), options["progress_every"], log_file
        )
        reporter.start()
        for done, issue in enumerate(stale.iterator(chunk_size=100), start=1):
            text = passage_text(f"{issue.title}\n{issue.description}")
            EmbeddingJob.objects.update_or_create(
                issue=issue,
                defaults={
                    "masked_text": text,
                    "content_hash": sha256(text.encode()).hexdigest(),
                    "status": "pending",
                },
            )
            reporter.item(done)
        reporter.finish()

        completed = 0
        jobs = EmbeddingJob.objects.filter(status="pending").select_related("issue")
        reporter = ProgressReporter(
            "embedding jobs", jobs.count(), options["progress_every"], log_file
        )
        reporter.start()
        local_model = None
        if options["embed_locally"]:
            try:
                local_model = self._local_embedder()
            except (ImportError, OSError, FileNotFoundError) as exc:
                reason = (
                    "sentence-transformers is not installed"
                    if isinstance(exc, ImportError)
                    else "local checkpoint is missing or unreadable"
                )
                reporter.warning(
                    f"Embedding unavailable: {reason}. Set ML_MODELS_DIR to a local checkpoint or run with the ML service configured."
                )
                reporter.finish()
                return
        warned_unavailable = False
        for done, job in enumerate(jobs.iterator(chunk_size=50), start=1):
            vectors = (
                local_model.encode(
                    [embedding_input(job.masked_text)], normalize_embeddings=True
                ).tolist()
                if local_model is not None
                else _ml_embeddings([embedding_input(job.masked_text)])
            )
            if not vectors or len(vectors[0]) != VECTOR_DIMENSION:
                if not warned_unavailable and local_model is None:
                    reporter.warning(
                        "Embedding unavailable: no valid vector returned. Configure ML_SERVICE_URL or run with --embed-locally and ML_MODELS_DIR pointing to a local checkpoint."
                    )
                    warned_unavailable = True
                reporter.item(done)
                continue
            issue = job.issue
            issue.embedding = vectors[0]
            issue.embedding_model_id = MODEL_ID
            issue.embedding_preprocessing_version = PREPROCESSING_VERSION
            issue.embedding_dimension = VECTOR_DIMENSION
            issue.save(
                update_fields=[
                    "embedding",
                    "embedding_model_id",
                    "embedding_preprocessing_version",
                    "embedding_dimension",
                    "updated_at",
                ]
            )
            job.status = "complete"
            job.save(update_fields=["status", "updated_at"])
            completed += 1
            reporter.item(done)
        reporter.finish()
        remaining = EmbeddingJob.objects.filter(status="pending").count()
        self.stdout.write(f"Embedded {completed} requests; {remaining} remain pending.")
