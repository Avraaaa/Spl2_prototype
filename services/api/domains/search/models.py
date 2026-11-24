from django.conf import settings
from django.db import models
from pgvector.django import VectorField

from domains.issues.models import Issue
from domains.tenants.models import Organization


class Label(models.Model):
    name = models.CharField(max_length=80, unique=True)
    description = models.CharField(max_length=300, blank=True)
    keywords = models.JSONField(default=list, blank=True)
    confidence_threshold = models.FloatField(default=0.55)
    is_active = models.BooleanField(default=True)
    color = models.CharField(max_length=7, default="#64748B")
    updated_at = models.DateTimeField(auto_now=True)
    embedding = VectorField(dimensions=384, null=True, blank=True)
    embedding_model_id = models.CharField(max_length=120, blank=True)
    embedding_preprocessing_version = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["name"]


class DisplayColor(models.Model):
    class Kind(models.TextChoices):
        REQUEST_TYPE = "request_type", "Request type"
        STATUS = "status", "Status"

    kind = models.CharField(max_length=20, choices=Kind.choices)
    key = models.CharField(max_length=24)
    color = models.CharField(max_length=7, default="#64748B")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["kind", "key"], name="unique_display_color_kind_key")
        ]


class LabelConfidenceThreshold(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    label = models.ForeignKey(Label, on_delete=models.CASCADE)
    threshold = models.FloatField(default=0.55)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "label"], name="unique_org_label_threshold"
            )
        ]


class SuggestionFeedback(models.Model):
    class Kind(models.TextChoices):
        DUPLICATE = "duplicate", "Duplicate"
        LABEL = "label", "Label"

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    issue = models.ForeignKey(Issue, null=True, blank=True, on_delete=models.PROTECT)
    candidate_issue = models.ForeignKey(
        Issue, null=True, blank=True, on_delete=models.PROTECT, related_name="suggestion_feedback"
    )
    label = models.ForeignKey(Label, null=True, blank=True, on_delete=models.PROTECT)
    accepted = models.BooleanField()
    score = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class IssueLabelSelection(models.Model):
    """The latest human-confirmed label for a request."""

    issue = models.OneToOneField(Issue, on_delete=models.PROTECT, related_name="label_selection")
    label = models.ForeignKey(Label, on_delete=models.PROTECT, related_name="issue_selections")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    selected_at = models.DateTimeField(auto_now=True)


class DuplicateReview(models.Model):
    class Decision(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmed duplicate"
        RECURRING = "recurring", "Marked recurring"
        DISMISSED = "dismissed", "Dismissed"

    issue = models.ForeignKey(Issue, on_delete=models.PROTECT, related_name="duplicate_reviews")
    candidate_issue = models.ForeignKey(
        Issue, on_delete=models.PROTECT, related_name="duplicate_candidates"
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    decision = models.CharField(max_length=20, choices=Decision.choices)
    created_at = models.DateTimeField(auto_now_add=True)


class TopicProposal(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="topic_proposals"
    )
    title = models.CharField(max_length=160)
    keywords = models.JSONField(default=list)
    issue_ids = models.JSONField(default=list)
    representatives = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, default="proposed")
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT
    )
    created_at = models.DateTimeField(auto_now_add=True)


class EmbeddingJob(models.Model):
    """Idempotent transactional outbox containing masked, prefixed text only."""

    issue = models.OneToOneField(Issue, on_delete=models.CASCADE, related_name="embedding_job")
    masked_text = models.TextField()
    content_hash = models.CharField(max_length=64)
    status = models.CharField(max_length=16, default="pending")
    attempts = models.PositiveSmallIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)
