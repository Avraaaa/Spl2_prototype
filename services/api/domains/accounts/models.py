from typing import Any

from django.conf import settings
from django.db import models

from domains.tenants.models import Organization

from .roles import Role


class Account(models.Model):
    """Portal profile for a Django user: the single organization the user belongs to and
    the first-login credential state. Users without an Account have no portal access."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="account"
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="accounts"
    )
    full_name = models.CharField(max_length=200)
    must_change_password = models.BooleanField(default=True)
    temporary_password_expires_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.full_name} @ {self.organization.code}"


class Membership(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="memberships"
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "organization", "role"], name="unique_user_org_role"
            )
        ]


class AccountEvent(models.Model):
    """Append-only onboarding/credential audit trail. Never stores credentials."""

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="+"
    )
    subject = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    kind = models.CharField(max_length=40)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.pk is not None:
            raise ValueError("AccountEvent is append-only")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> Any:
        raise ValueError("AccountEvent is append-only")
