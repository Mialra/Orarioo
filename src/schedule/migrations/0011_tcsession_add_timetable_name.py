from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("schedule", "0010_add_tc_session"),
    ]

    operations = [
        migrations.AddField(
            model_name="tcsession",
            name="name",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="tcsession",
            name="observations",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddIndex(
            model_name="tcsession",
            index=models.Index(
                fields=["team", "observations"],
                name="tc_session_team_id_obs_idx",
            ),
        ),
    ]
