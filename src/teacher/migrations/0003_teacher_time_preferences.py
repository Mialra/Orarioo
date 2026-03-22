from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("teacher", "0002_ensure_teacher_table"),
    ]

    operations = [
        migrations.AddField(
            model_name="teacher",
            name="time_preferences",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
