from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("issues", "0004_issue_embedding")]

    operations = [
        migrations.CreateModel(
            name="MaskingPattern",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100, unique=True)),
                ("pattern", models.CharField(max_length=200)),
                ("replacement", models.CharField(default="[SENSITIVE]", max_length=80)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["name"],
                "permissions": [
                    (
                        "view_unmasked_original",
                        "Can view unmasked original issue text",
                    )
                ],
            },
        ),
    ]
