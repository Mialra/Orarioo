import django.db.models.deletion
from django.db import migrations, models


def assert_no_null_team(apps, schema_editor):
    Classroom = apps.get_model("classroom", "Classroom")
    if Classroom.objects.filter(team__isnull=True).exists():
        raise RuntimeError(
            "Cannot make classroom.team non-null while Classroom rows with NULL team exist."
        )


class Migration(migrations.Migration):

    dependencies = [
        ("classroom", "0008_remove_classroom_is_shared"),
        ("user", "0015_collaborationteam_schedule_config"),
    ]

    operations = [
        migrations.RunPython(assert_no_null_team, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="classroom",
            name="team",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="%(app_label)s_%(class)s_items",
                to="user.collaborationteam",
            ),
        ),
    ]
