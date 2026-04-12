# Generated manually on 2026-04-12

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("schedule", "0005_schedule_team"),
    ]

    operations = [
        migrations.CreateModel(
            name="ScheduleDefect",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("defect_code", models.CharField(choices=[("GAP_IN_GROUP", "Gap in Group"), ("UNMET_SUBJECT_PREF", "Unmet Subject Preference"), ("UNMET_TEACHER_PREF", "Unmet Teacher Preference"), ("TEACHER_GAP", "Teacher Internal Gap"), ("SUBOPTIMAL_TC", "Suboptimal TC Distribution")], max_length=50)),
                ("severity", models.CharField(choices=[("INFO", "Informational"), ("WARNING", "Warning")], default="WARNING", max_length=20)),
                ("entity_type", models.CharField(max_length=50)),
                ("entity_id", models.IntegerField(blank=True, null=True)),
                ("entity_name", models.CharField(max_length=255)),
                ("description", models.TextField()),
                ("context", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("schedule", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="defects", to="schedule.schedule")),
            ],
            options={
                "db_table": "schedule_defect",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="scheduledefect",
            index=models.Index(fields=["schedule", "defect_code"], name="schedule_de_schedule_defect_code_idx"),
        ),
        migrations.AddIndex(
            model_name="scheduledefect",
            index=models.Index(fields=["entity_type", "entity_id"], name="schedule_de_entity_type_entity_id_idx"),
        ),
        migrations.AddConstraint(
            model_name="scheduledefect",
            constraint=models.UniqueConstraint(fields=("schedule", "defect_code", "entity_id"), name="unique_schedule_defect"),
        ),
    ]
