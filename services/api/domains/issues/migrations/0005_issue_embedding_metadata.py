from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("issues", "0006_issueoriginaltext")]

    operations = [
        migrations.AddField(
            model_name="issue",
            name="embedding_model_id",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="issue",
            name="embedding_preprocessing_version",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="issue",
            name="embedding_dimension",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
    ]
