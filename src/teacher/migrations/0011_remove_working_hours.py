from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("teacher", "0010_require_team"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="teacher",
            name="working_hours",
        ),
    ]
