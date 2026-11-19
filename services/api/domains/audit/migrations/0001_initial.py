from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("issues", "0003_issue_recurring_of"),
        ("tenants", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditAnchor",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sequence", models.PositiveBigIntegerField()),
                ("record_hash", models.CharField(max_length=64)),
                ("anchored_at", models.DateTimeField(auto_now_add=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="audit_anchors", to="tenants.organization")),
            ],
        ),
        migrations.CreateModel(
            name="AuditRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sequence", models.PositiveBigIntegerField()),
                ("action", models.CharField(max_length=80)),
                ("payload", models.JSONField(default=dict)),
                ("previous_hash", models.CharField(blank=True, max_length=64)),
                ("record_hash", models.CharField(max_length=64, unique=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="audit_records", to="tenants.organization")),
            ],
            options={"ordering": ["organization_id", "sequence"]},
        ),
        migrations.AddConstraint(
            model_name="auditrecord",
            constraint=models.UniqueConstraint(fields=("organization", "sequence"), name="unique_audit_sequence"),
        ),
    ]
