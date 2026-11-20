from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("issues", "0004_issue_embedding"),
        ("search", "0003_merge_0002_issuelabelselection_0002_topicproposal"),
    ]

    operations = [
        migrations.CreateModel(
            name="DuplicateReview",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "decision",
                    models.CharField(
                        choices=[
                            ("confirmed", "Confirmed duplicate"),
                            ("recurring", "Marked recurring"),
                            ("dismissed", "Dismissed"),
                        ],
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "candidate_issue",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="duplicate_candidates",
                        to="issues.issue",
                    ),
                ),
                (
                    "issue",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="duplicate_reviews",
                        to="issues.issue",
                    ),
                ),
            ],
        ),
    ]
