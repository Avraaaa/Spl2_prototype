from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import domains.attachments.models


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL), ("issues", "0002_workflow"), ("comments", "0001_initial")]
    operations = [migrations.CreateModel(name="Attachment", fields=[
        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("file", models.FileField(upload_to=domains.attachments.models.private_path)),
        ("original_name", models.CharField(max_length=255)),
        ("content_type", models.CharField(max_length=100)),
        ("size", models.PositiveIntegerField()),
        ("quarantine_status", models.CharField(default="unscanned", max_length=20)),
        ("created_at", models.DateTimeField(auto_now_add=True)),
        ("comment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="attachments", to="comments.comment")),
        ("issue", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="attachments", to="issues.issue")),
        ("uploaded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
    ])]
