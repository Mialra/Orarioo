import django.db.models.deletion
from django.db import migrations, models


def _assign_group_to_existing_subjects(apps, schema_editor):
    Subject = apps.get_model("subject", "Subject")
    Group = apps.get_model("group", "Group")

    # Best-effort backfill for existing rows before making field mandatory.
    first_group = Group.objects.order_by("id").first()
    if first_group is None:
        return

    for subject in Subject.objects.filter(group__isnull=True):
        subject.group_id = first_group.id
        subject.save(update_fields=["group"])


class Migration(migrations.Migration):

    dependencies = [
        ("group", "0001_initial"),
        ("subject", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="subject",
            name="group",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="subjects",
                to="group.group",
            ),
        ),
        migrations.RunPython(
            _assign_group_to_existing_subjects, migrations.RunPython.noop
        ),
        migrations.AlterField(
            model_name="subject",
            name="group",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="subjects",
                to="group.group",
            ),
        ),
    ]
