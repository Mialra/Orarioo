import django.db.models.deletion
from django.db import migrations, models


def assert_no_null_mandatory_classroom(apps, schema_editor):
    Subject = apps.get_model("subject", "Subject")
    if Subject.objects.filter(mandatory_classroom__isnull=True).exists():
        raise RuntimeError(
            "Cannot make subject.mandatory_classroom non-null while Subject rows "
            "with NULL mandatory_classroom exist."
        )


class Migration(migrations.Migration):

    dependencies = [
        ("classroom", "0009_require_team"),
        ("subject", "0018_require_team"),
    ]

    operations = [
        migrations.RunPython(
            assert_no_null_mandatory_classroom,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="subject",
            name="mandatory_classroom",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="mandatory_subjects",
                to="classroom.classroom",
            ),
        ),
    ]
