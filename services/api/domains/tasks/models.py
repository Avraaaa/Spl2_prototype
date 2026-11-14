from django.conf import settings
from django.db import models

from domains.issues.models import Issue


class InternalTask(models.Model):
    class Status(models.TextChoices):
        TODO = "todo", "To do"
        IN_PROGRESS = "in_progress", "In progress"
        DONE = "done", "Done"

    issue = models.ForeignKey(Issue, on_delete=models.PROTECT, related_name="internal_tasks")
    title = models.CharField(max_length=200)
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="internal_tasks",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TODO)
    commit_url = models.URLField(max_length=500, blank=True)
    pull_request_url = models.URLField(max_length=500, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_internal_tasks"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class InternalNote(models.Model):
    issue = models.ForeignKey(Issue, on_delete=models.PROTECT, related_name="internal_notes")
    task = models.ForeignKey(
        InternalTask, on_delete=models.PROTECT, null=True, blank=True, related_name="notes"
    )
    body = models.TextField()
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
