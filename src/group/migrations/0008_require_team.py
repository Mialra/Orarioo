import django.db.models.deletion
from django.db import migrations, models


def assert_no_null_team(apps, schema_editor):
    Group = apps.get_model("group", "Group")
    if Group.objects.filter(team__isnull=True).exists():
        raise RuntimeError(
            "Cannot make group.team non-null while Group rows with NULL team exist."
        )


class Migration(migrations.Migration):

    dependencies = [
        ("group", "0007_remove_group_group_name_ci_unique_and_more"),
        ("user", "0015_collaborationteam_schedule_config"),
    ]

    operations = [
        migrations.RunPython(assert_no_null_team, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="group",
            name="team",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="%(app_label)s_%(class)s_items",
                to="user.collaborationteam",
            ),
        ),
    ]
