import uuid
from pathlib import Path

from django.conf import settings
from django.db import models

from domains.comments.models import Comment
from domains.issues.models import Issue


def private_path(instance, filename):
    suffix = Path(filename).suffix.lower()
    return f"private/{uuid.uuid4().hex}{suffix}"


class Attachment(models.Model):
    issue = models.ForeignKey(Issue, on_delete=models.PROTECT, related_name="attachments")
    comment = models.ForeignKey(
        Comment, on_delete=models.PROTECT, null=True, blank=True, related_name="attachments"
    )
    file = models.FileField(upload_to=private_path)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size = models.PositiveIntegerField()
    quarantine_status = models.CharField(max_length=20, default="QUARANTINED")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
