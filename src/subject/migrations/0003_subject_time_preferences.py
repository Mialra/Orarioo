from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("subject", "0002_subject_group"),
    ]

    operations = [
        migrations.AddField(
            model_name="subject",
            name="time_preferences",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
