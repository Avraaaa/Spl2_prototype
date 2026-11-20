import pgvector.django
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("issues", "0003_issue_recurring_of")]

    operations = [
        migrations.AddField(
            model_name="issue",
            name="embedding",
            field=pgvector.django.VectorField(blank=True, dimensions=384, null=True),
        ),
    ]
