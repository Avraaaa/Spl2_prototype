from django.db import migrations, models


def backfill_contact_email(apps, schema_editor):
    Organization = apps.get_model("tenants", "Organization")
    for organization in Organization.objects.all().iterator():
        organization.contact_email = f"contact-{organization.pk}@placeholder.invalid"
        organization.contact_email_placeholder = True
        organization.save(update_fields=["contact_email", "contact_email_placeholder"])


class Migration(migrations.Migration):
    dependencies = [("tenants", "0001_initial")]
    operations = [
        migrations.AddField(
            model_name="organization",
            name="contact_email",
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name="organization",
            name="contact_email_placeholder",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(backfill_contact_email, migrations.RunPython.noop),
    ]
