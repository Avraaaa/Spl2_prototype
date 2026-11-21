"""Versioned text preparation and transactional embedding outbox helpers."""

import hashlib

from domains.issues.services import mask_sensitive

MODEL_ID = "multilingual-e5-small"
PREPROCESSING_VERSION = "masked-e5-v1"
VECTOR_DIMENSION = 384


def passage_text(value: str) -> str:
    return f"passage: {mask_sensitive(value)}"


def query_text(value: str) -> str:
    return f"query: {mask_sensitive(value)}"


def queue_issue_embedding(issue) -> None:
    """Upsert a masked embedding job in the caller's issue transaction."""
    from .models import EmbeddingJob

    text = passage_text(f"{issue.title}\n{issue.description}")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    existing = EmbeddingJob.objects.filter(issue=issue).first()
    if existing is not None and existing.content_hash == digest:
        vector_is_current = (
            issue.embedding is not None
            and issue.embedding_model_id == MODEL_ID
            and issue.embedding_preprocessing_version == PREPROCESSING_VERSION
            and issue.embedding_dimension == VECTOR_DIMENSION
        )
        if existing.status == "pending" or vector_is_current:
            return
    issue.embedding = None
    issue.embedding_model_id = ""
    issue.embedding_preprocessing_version = ""
    issue.embedding_dimension = None
    issue.save(
        update_fields=[
            "embedding",
            "embedding_model_id",
            "embedding_preprocessing_version",
            "embedding_dimension",
            "updated_at",
        ]
    )
    EmbeddingJob.objects.update_or_create(
        issue=issue,
        defaults={"masked_text": text, "content_hash": digest, "status": "pending", "attempts": 0},
    )
