import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("tenants", "0001_initial"),
        ("products", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="Issue",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference", models.CharField(blank=True, max_length=32, null=True, unique=True)),
                ("title", models.CharField(blank=True, max_length=200)),
                ("description", models.TextField(blank=True)),
                ("request_type", models.CharField(blank=True, choices=[("BUG", "Bug"), ("CHANGE", "Change"), ("FEATURE", "Feature"), ("SUPPORT", "Support")], max_length=10)),
                ("priority", models.CharField(blank=True, choices=[("LOW", "Low"), ("MEDIUM", "Medium"), ("HIGH", "High"), ("CRITICAL", "Critical")], max_length=10)),
                ("environment", models.TextField(blank=True)),
                ("steps_to_reproduce", models.TextField(blank=True)),
                ("expected_result", models.TextField(blank=True)),
                ("actual_result", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("DRAFT", "Draft"), ("SUBMITTED", "Submitted")], default="DRAFT", max_length=20)),
                ("version", models.PositiveIntegerField(default=1)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_issues", to=settings.AUTH_USER_MODEL)),
                ("module", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="products.module")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="issues", to="tenants.organization")),
                ("product", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="products.product")),
                ("related_request", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="issues.issue")),
                ("submitted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="submitted_issues", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.CreateModel(
            name="IssueEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(max_length=40)),
                ("from_status", models.CharField(max_length=20)),
                ("to_status", models.CharField(max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("issue", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="events", to="issues.issue")),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
    ]
