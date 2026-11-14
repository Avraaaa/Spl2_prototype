from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("issues", "0002_workflow")]

    operations = [
        migrations.AddField(
            model_name="issue",
            name="recurring_of",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="recurring_requests",
                to="issues.issue",
            ),
        ),
    ]
