import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("classroom", "0009_require_team"),
        ("subject", "0019_require_mandatory_classroom"),
    ]

    operations = [
        migrations.RenameField(
            model_name="subject",
            old_name="mandatory_classroom",
            new_name="classroom",
        ),
        migrations.AlterField(
            model_name="subject",
            name="classroom",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="subjects",
                to="classroom.classroom",
            ),
        ),
    ]
