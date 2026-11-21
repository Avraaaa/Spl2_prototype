from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("search", "0005_embeddingjob_and_label_embedding")]

    operations = [migrations.RunSQL("CREATE EXTENSION IF NOT EXISTS pg_trgm", migrations.RunSQL.noop)]
