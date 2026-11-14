from django.db import models


class OrganizationKind(models.TextChoices):
    DATASOFT = "DATASOFT", "DataSoft"
    BANK = "BANK", "Client bank"


class Organization(models.Model):
    """A tenant. Exactly one DATASOFT organization exists; every client bank is a BANK row.
    Bank membership is always derived server-side from the authenticated user's account."""

    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=20, unique=True)
    kind = models.CharField(max_length=10, choices=OrganizationKind.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["kind", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["kind"],
                condition=models.Q(kind="DATASOFT"),
                name="single_datasoft_organization",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"
