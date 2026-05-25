import django.db.models.deletion
from django.db import migrations, models


def assert_no_null_team(apps, schema_editor):
    Teacher = apps.get_model("teacher", "Teacher")
    if Teacher.objects.filter(team__isnull=True).exists():
        raise RuntimeError(
            "Cannot make teacher.team non-null while Teacher rows with NULL team exist."
        )


class Migration(migrations.Migration):

    dependencies = [
        ("teacher", "0009_teacher_max_weekly_minutes_and_more"),
        ("user", "0015_collaborationteam_schedule_config"),
    ]

    operations = [
        migrations.RunPython(assert_no_null_team, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="teacher",
            name="team",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="%(app_label)s_%(class)s_items",
                to="user.collaborationteam",
            ),
        ),
    ]
