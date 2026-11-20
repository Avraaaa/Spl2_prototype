from django.conf import settings
from django.db import models

from domains.issues.models import Issue
from domains.tenants.models import Organization


class Label(models.Model):
    name = models.CharField(max_length=80, unique=True)
    description = models.CharField(max_length=300, blank=True)
    keywords = models.JSONField(default=list, blank=True)
    confidence_threshold = models.FloatField(default=0.55)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]


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

    issue = models.OneToOneField(
        Issue, on_delete=models.PROTECT, related_name="label_selection"
    )
    label = models.ForeignKey(Label, on_delete=models.PROTECT, related_name="issue_selections")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    selected_at = models.DateTimeField(auto_now=True)


class TopicProposal(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="topic_proposals"
    )
    title = models.CharField(max_length=160)
    keywords = models.JSONField(default=list)
    issue_ids = models.JSONField(default=list)
    status = models.CharField(max_length=20, default="proposed")
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT
    )
    created_at = models.DateTimeField(auto_now_add=True)
