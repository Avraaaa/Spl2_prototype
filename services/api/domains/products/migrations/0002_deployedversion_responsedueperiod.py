import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("products", "0001_initial"), ("tenants", "0001_initial")]
    operations = [
        migrations.CreateModel(name="DeployedVersion", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("version", models.CharField(max_length=80)), ("deployed_at", models.DateField()), ("created_at", models.DateTimeField(auto_now_add=True)), ("module", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="deployments", to="products.module")), ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="deployed_versions", to="tenants.organization")), ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="deployments", to="products.product"))], options={"ordering": ["-deployed_at", "-id"]}),
        migrations.CreateModel(name="ResponseDuePeriod", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("priority", models.CharField(max_length=10, unique=True)), ("days", models.PositiveSmallIntegerField())], options={"ordering": ["priority"]}),
    ]
