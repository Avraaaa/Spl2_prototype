from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("issues", "0007_issue_acceptance_criteria")]

    operations = [
        migrations.AddField(
            model_name="issue",
            name="is_synthetic",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="issue",
            name="synthetic_key",
            field=models.CharField(blank=True, db_index=True, max_length=64),
        ),
    ]
