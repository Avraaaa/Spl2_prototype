"""Transactional mutations for client-visible issue comments."""

from django.contrib.auth.models import User
from django.db import transaction

from domains.issues.models import Issue
from domains.issues.services import mask_sensitive
from domains.notifications import services as notification_services

from .models import Comment


@transaction.atomic
def create_comment(*, issue: Issue, author: User, body: str) -> Comment:
    """Persist a masked comment and its alerts in one transaction."""
    comment = Comment.objects.create(
        issue=issue,
        author=author,
        body=mask_sensitive(body),
    )
    notification_services.notify_comment(comment)
    return comment
