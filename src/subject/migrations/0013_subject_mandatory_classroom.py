import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("classroom", "0007_remove_classroom_classroom_name_ci_unique_and_more"),
        ("subject", "0012_remove_subject_subject_name_ci_unique_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="subject",
            name="allowed_classrooms",
        ),
        migrations.AddField(
            model_name="subject",
            name="mandatory_classroom",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="mandatory_subjects",
                to="classroom.classroom",
            ),
        ),
    ]
