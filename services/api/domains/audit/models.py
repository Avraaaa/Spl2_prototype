from django.conf import settings
from django.db import models
from django.utils import timezone

from domains.tenants.models import Organization


class AuditRecord(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="audit_records"
    )
    sequence = models.PositiveBigIntegerField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=80)
    payload = models.JSONField(default=dict)
    previous_hash = models.CharField(max_length=64, blank=True)
    record_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["organization_id", "sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "sequence"], name="unique_audit_sequence"
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError("AuditRecord is append-only")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("AuditRecord is append-only")


class AuditAnchor(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="audit_anchors"
    )
    sequence = models.PositiveBigIntegerField()
    record_hash = models.CharField(max_length=64)
    external_reference = models.CharField(max_length=128, blank=True)
    anchored_at = models.DateTimeField(auto_now_add=True)
