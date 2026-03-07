from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("classroom", "0001_initial"),
        ("group", "0001_initial"),
        ("teacher", "0002_ensure_teacher_table"),
        ("user", "0002_user_name_from_namedentity"),
    ]

    operations = [
        migrations.CreateModel(
            name="Schedule",
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
                ("name", models.CharField(max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.CharField(blank=True, max_length=150)),
                ("updated_by", models.CharField(blank=True, max_length=150)),
                ("start_time", models.DateTimeField()),
                ("end_time", models.DateTimeField()),
                ("observations", models.TextField(blank=True)),
                (
                    "classroom",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="schedules",
                        to="classroom.classroom",
                    ),
                ),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="schedules",
                        to="group.group",
                    ),
                ),
                (
                    "teacher",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="schedules",
                        to="teacher.teacher",
                    ),
                ),
                (
                    "users",
                    models.ManyToManyField(related_name="schedules", to="user.user"),
                ),
            ],
            options={
                "db_table": "schedule",
                "ordering": ["start_time", "id"],
            },
        ),
    ]
