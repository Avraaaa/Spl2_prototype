from django.db.models.signals import post_save
from django.dispatch import receiver

from domains.issues.models import IssueEvent

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
