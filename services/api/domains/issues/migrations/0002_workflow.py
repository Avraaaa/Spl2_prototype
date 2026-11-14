import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("issues", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkflowSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reopen_days", models.PositiveIntegerField(default=30)),
            ],
        ),
        migrations.AddField(
            model_name="issue",
            name="actual_delivery_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="issue",
            name="assignee",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="assigned_issues", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="issue",
            name="closed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="issue",
            name="delivery_note",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="issue",
            name="deployment_details",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="issue",
            name="last_status_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="issue",
            name="tentative_delivery_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="issue",
            name="tentative_delivery_later",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="issueevent",
            name="details",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="issueevent",
            name="reason",
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name="issue",
            name="status",
            field=models.CharField(choices=[("DRAFT", "Draft"), ("SUBMITTED", "Submitted"), ("ACCEPTED", "Accepted"), ("REJECTED", "Rejected"), ("PENDING", "Pending"), ("IN_PROGRESS", "In progress"), ("AWAITING_VERIFICATION", "Awaiting client verification"), ("VERIFIED", "Verified"), ("CLOSED", "Closed")], default="DRAFT", max_length=24),
        ),
        migrations.AlterField(
            model_name="issueevent",
            name="from_status",
            field=models.CharField(max_length=24),
        ),
        migrations.AlterField(
            model_name="issueevent",
            name="to_status",
            field=models.CharField(max_length=24),
        ),
    ]
