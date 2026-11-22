from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("attachments", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="attachment",
            name="quarantine_status",
            field=models.CharField(default="QUARANTINED", max_length=20),
        ),
        migrations.RunSQL(
            sql="UPDATE attachments_attachment SET quarantine_status = 'QUARANTINED' WHERE quarantine_status = 'unscanned'",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
