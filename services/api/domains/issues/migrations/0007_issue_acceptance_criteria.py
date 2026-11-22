from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("issues", "0005_issue_embedding_metadata")]

    operations = [
        migrations.AddField(
            model_name="issue",
            name="acceptance_criteria",
            field=models.TextField(blank=True),
        ),
    ]
