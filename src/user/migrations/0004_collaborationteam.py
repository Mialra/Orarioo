from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0003_rename_director_role_to_direccion"),
    ]

    operations = [
        migrations.CreateModel(
            name="CollaborationTeam",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=150)),
                (
                    "members",
                    models.ManyToManyField(
                        blank=True,
                        related_name="collaboration_teams",
                        to="user.user",
                    ),
                ),
            ],
            options={
                "db_table": "collaboration_team",
                "ordering": ["name", "id"],
            },
        ),
    ]
