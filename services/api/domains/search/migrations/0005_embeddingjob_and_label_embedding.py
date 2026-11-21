import pgvector.django
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("issues", "0005_issue_embedding_metadata"),
        ("search", "0004_duplicatereview"),
    ]

    operations = [
        migrations.AddField(
            model_name="topicproposal",
            name="representatives",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="label",
            name="embedding",
            field=pgvector.django.VectorField(blank=True, dimensions=384, null=True),
        ),
        migrations.AddField(
            model_name="label",
            name="embedding_model_id",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="label",
            name="embedding_preprocessing_version",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.CreateModel(
            name="LabelConfidenceThreshold",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("threshold", models.FloatField(default=0.55)),
                ("label", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="search.label")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="tenants.organization")),
            ],
        ),
        migrations.AddConstraint(
            model_name="labelconfidencethreshold",
            constraint=models.UniqueConstraint(fields=("organization", "label"), name="unique_org_label_threshold"),
        ),
        migrations.CreateModel(
            name="EmbeddingJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("masked_text", models.TextField()),
                ("content_hash", models.CharField(max_length=64)),
                ("status", models.CharField(default="pending", max_length=16)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("issue", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="embedding_job", to="issues.issue")),
            ],
        ),
    ]
