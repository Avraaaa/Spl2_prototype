from typing import Any

from django.conf import settings
from django.db import models

from domains.products.models import Module, Product
from domains.tenants.models import Organization


class RequestType(models.TextChoices):
    BUG = "BUG", "Bug"
    CHANGE = "CHANGE", "Change"
    FEATURE = "FEATURE", "Feature"
    SUPPORT = "SUPPORT", "Support"


class Priority(models.TextChoices):
    LOW = "LOW", "Low"
    MEDIUM = "MEDIUM", "Medium"
    HIGH = "HIGH", "High"
    CRITICAL = "CRITICAL", "Critical"


class IssueStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    SUBMITTED = "SUBMITTED", "Submitted"


class Issue(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="issues")
    # The primary key comes from PostgreSQL's sequence; reference is assigned once after insert.
    reference = models.CharField(max_length=32, unique=True, null=True, blank=True)
    title = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    request_type = models.CharField(max_length=10, choices=RequestType.choices, blank=True)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, null=True, blank=True)
    module = models.ForeignKey(Module, on_delete=models.PROTECT, null=True, blank=True)
    priority = models.CharField(max_length=10, choices=Priority.choices, blank=True)
    environment = models.TextField(blank=True)
    steps_to_reproduce = models.TextField(blank=True)
    expected_result = models.TextField(blank=True)
    actual_result = models.TextField(blank=True)
    related_request = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True)
    status = models.CharField(max_length=20, choices=IssueStatus.choices, default=IssueStatus.DRAFT)
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_issues"
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="submitted_issues",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class IssueEvent(models.Model):
    issue = models.ForeignKey(Issue, on_delete=models.PROTECT, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    kind = models.CharField(max_length=40)
    from_status = models.CharField(max_length=20)
    to_status = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.pk is not None:
            raise ValueError("IssueEvent is append-only")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> Any:
        raise ValueError("IssueEvent is append-only")
