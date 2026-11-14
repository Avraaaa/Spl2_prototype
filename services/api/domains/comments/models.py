from django.conf import settings
from django.db import models

from domains.issues.models import Issue


class Comment(models.Model):
    issue = models.ForeignKey(Issue, on_delete=models.PROTECT, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
