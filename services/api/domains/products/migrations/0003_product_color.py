from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("products", "0002_deployedversion_responsedueperiod")]

    operations = [
        migrations.AddField(
            model_name="product",
            name="color",
            field=models.CharField(default="#64748B", max_length=7),
        ),
    ]
