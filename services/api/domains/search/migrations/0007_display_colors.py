from django.db import migrations, models


TYPE_COLORS = {
    "BUG": "#DC2626",
    "CHANGE": "#7C3AED",
    "FEATURE": "#2563EB",
    "SUPPORT": "#0891B2",
}
STATUS_COLORS = {
    "DRAFT": "#64748B",
    "SUBMITTED": "#D97706",
    "ACCEPTED": "#2563EB",
    "REJECTED": "#DC2626",
    "PENDING": "#CA8A04",
    "IN_PROGRESS": "#7C3AED",
    "AWAITING_VERIFICATION": "#0891B2",
    "VERIFIED": "#16A34A",
    "CLOSED": "#475569",
}


def seed_colors(apps, schema_editor):
    DisplayColor = apps.get_model("search", "DisplayColor")
    for key, color in TYPE_COLORS.items():
        DisplayColor.objects.get_or_create(
            kind="request_type", key=key, defaults={"color": color}
        )
    for key, color in STATUS_COLORS.items():
        DisplayColor.objects.get_or_create(kind="status", key=key, defaults={"color": color})


class Migration(migrations.Migration):
    dependencies = [
        ("search", "0006_enable_pg_trgm"),
        ("products", "0003_product_color"),
    ]

    operations = [
        migrations.AddField(
            model_name="label",
            name="color",
            field=models.CharField(default="#64748B", max_length=7),
        ),
        migrations.CreateModel(
            name="DisplayColor",
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
                (
                    "kind",
                    models.CharField(
                        choices=[("request_type", "Request type"), ("status", "Status")],
                        max_length=20,
                    ),
                ),
                ("key", models.CharField(max_length=24)),
                ("color", models.CharField(default="#64748B", max_length=7)),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("kind", "key"), name="unique_display_color_kind_key"
                    )
                ]
            },
        ),
        migrations.RunPython(seed_colors, migrations.RunPython.noop),
    ]
