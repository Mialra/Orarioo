import django.db.models.deletion
from django.db import migrations, models


def assert_no_null_team(apps, schema_editor):
    Subject = apps.get_model("subject", "Subject")
    if Subject.objects.filter(team__isnull=True).exists():
        raise RuntimeError(
            "Cannot make subject.team non-null while Subject rows with NULL team exist."
        )


class Migration(migrations.Migration):

    dependencies = [
        ("subject", "0017_remove_preferred_time_slot"),
        ("user", "0015_collaborationteam_schedule_config"),
    ]

    operations = [
        migrations.RunPython(assert_no_null_team, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="subject",
            name="team",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="%(app_label)s_%(class)s_items",
                to="user.collaborationteam",
            ),
        ),
    ]
