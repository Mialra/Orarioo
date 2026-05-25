import django.db.models.deletion
from django.db import migrations, models


def assert_no_null_team(apps, schema_editor):
    models_to_check = (
        ("Schedule", apps.get_model("schedule", "Schedule")),
        ("TCSession", apps.get_model("schedule", "TCSession")),
        ("ScheduleGenerationJob", apps.get_model("schedule", "ScheduleGenerationJob")),
    )
    orphaned = [
        model_name
        for model_name, model in models_to_check
        if model.objects.filter(team__isnull=True).exists()
    ]
    if orphaned:
        raise RuntimeError(
            "Cannot make schedule team fields non-null while rows with NULL team "
            f"exist in: {', '.join(orphaned)}."
        )


class Migration(migrations.Migration):

    dependencies = [
        ("schedule", "0014_schedulegenerationjob_current_phase"),
        ("user", "0015_collaborationteam_schedule_config"),
    ]

    operations = [
        migrations.RunPython(assert_no_null_team, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="schedule",
            name="team",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="%(app_label)s_%(class)s_items",
                to="user.collaborationteam",
            ),
        ),
        migrations.AlterField(
            model_name="tcsession",
            name="team",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="%(app_label)s_%(class)s_items",
                to="user.collaborationteam",
            ),
        ),
        migrations.AlterField(
            model_name="schedulegenerationjob",
            name="team",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="%(app_label)s_%(class)s_items",
                to="user.collaborationteam",
            ),
        ),
    ]
