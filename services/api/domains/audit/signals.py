from django.db.models.signals import post_save
from django.dispatch import receiver

from domains.attachments.models import Attachment
from domains.comments.models import Comment
from domains.issues.models import IssueEvent
from domains.tasks.models import InternalNote, InternalTask

from .services import append_record


@receiver(post_save, sender=IssueEvent)
def record_issue_event(sender, instance, created, **kwargs):
    if not created:
        return
    append_record(
        organization=instance.issue.organization,
        actor=instance.actor,
        action=f"issue.{instance.kind.lower()}",
        payload={
            "issue_id": instance.issue_id,
            "from_status": instance.from_status,
            "to_status": instance.to_status,
            "reason": instance.reason,
            "details": instance.details,
        },
    )


def _append_simple(*, instance, actor, action: str, payload: dict, created: bool) -> None:
    if not created:
        return
    append_record(
        organization=instance.issue.organization,
        actor=actor,
        action=action,
        payload=payload,
    )


@receiver(post_save, sender=Comment)
def record_comment(sender, instance, created, **kwargs):
    _append_simple(
        instance=instance,
        actor=instance.author,
        action="issue.comment",
        payload={"issue_id": instance.issue_id, "body_length": len(instance.body)},
        created=created,
    )


@receiver(post_save, sender=InternalTask)
def record_internal_task(sender, instance, created, **kwargs):
    _append_simple(
        instance=instance,
        actor=instance.created_by,
        action="issue.internal_task",
        payload={"issue_id": instance.issue_id, "task_id": instance.pk, "title": instance.title},
        created=created,
    )


@receiver(post_save, sender=InternalNote)
def record_internal_note(sender, instance, created, **kwargs):
    _append_simple(
        instance=instance,
        actor=instance.author,
        action="issue.internal_note",
        payload={"issue_id": instance.issue_id, "body_length": len(instance.body)},
        created=created,
    )


@receiver(post_save, sender=Attachment)
def record_attachment(sender, instance, created, **kwargs):
    _append_simple(
        instance=instance,
        actor=instance.uploaded_by,
        action="issue.attachment",
        payload={
            "issue_id": instance.issue_id,
            "attachment_id": instance.pk,
            "size": instance.size,
        },
        created=created,
    )
