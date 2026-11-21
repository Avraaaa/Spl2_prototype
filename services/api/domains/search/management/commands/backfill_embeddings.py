"""Process pending local embedding jobs and backfill eligible requests."""

from hashlib import sha256

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
from domains.search.services import _ml_embeddings


class Command(BaseCommand):
    help = "Backfill missing request embeddings using the configured local ML service."

    def handle(self, *args, **options):
        for issue in (
            Issue.objects.exclude(status=IssueStatus.DRAFT)
            .filter(embedding__isnull=True)
            .iterator(chunk_size=100)
        ):
            text = passage_text(f"{issue.title}\n{issue.description}")
            EmbeddingJob.objects.update_or_create(
                issue=issue,
                defaults={
                    "masked_text": text,
                    "content_hash": sha256(text.encode()).hexdigest(),
                    "status": "pending",
                },
            )

        stale = Issue.objects.exclude(status=IssueStatus.DRAFT).exclude(
            embedding_model_id=MODEL_ID,
            embedding_preprocessing_version=PREPROCESSING_VERSION,
            embedding_dimension=VECTOR_DIMENSION,
        )
        for issue in stale.iterator(chunk_size=100):
            text = passage_text(f"{issue.title}\n{issue.description}")
            EmbeddingJob.objects.update_or_create(
                issue=issue,
                defaults={
                    "masked_text": text,
                    "content_hash": sha256(text.encode()).hexdigest(),
                    "status": "pending",
                },
            )

        completed = 0
        jobs = EmbeddingJob.objects.filter(status="pending").select_related("issue")
        for job in jobs.iterator(chunk_size=50):
            vectors = _ml_embeddings([embedding_input(job.masked_text)])
            if not vectors or len(vectors[0]) != VECTOR_DIMENSION:
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
        remaining = EmbeddingJob.objects.filter(status="pending").count()
        self.stdout.write(f"Embedded {completed} requests; {remaining} remain pending.")
