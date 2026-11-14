from django.conf import settings
from django.db import models

from domains.issues.models import Issue
from domains.tenants.models import Organization


class Notification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    issue = models.ForeignKey(Issue, null=True, blank=True, on_delete=models.PROTECT)
    kind = models.CharField(max_length=40)
    title = models.CharField(max_length=200)
    body = models.TextField()
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class OutboxMessage(models.Model):
    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        IN_APP = "in_app", "In app"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        DEAD = "dead", "Dead"

    channel = models.CharField(max_length=8, choices=Channel.choices)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    payload = models.JSONField(default=dict)
    idempotency_key = models.CharField(max_length=200, unique=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField()
    locked_until = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["next_attempt_at", "id"]
