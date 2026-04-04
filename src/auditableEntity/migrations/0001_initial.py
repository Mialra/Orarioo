import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditEntry",
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
                ("entity_type", models.CharField(max_length=50)),
                ("entity_id", models.PositiveBigIntegerField()),
                ("entity_name", models.CharField(blank=True, max_length=255)),
                (
                    "action_type",
                    models.CharField(
                        choices=[
                            ("CREATE", "Create"),
                            ("UPDATE", "Update"),
                            ("DELETE", "Delete"),
                        ],
                        max_length=10,
                    ),
                ),
                ("detail", models.TextField()),
                ("changed_fields", models.JSONField(blank=True, default=list)),
                ("actor_email", models.EmailField(blank=True, max_length=254)),
                ("occurred_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_entries",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "audit_entry",
                "ordering": ["-occurred_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="auditentry",
            index=models.Index(
                fields=["entity_type", "entity_id"],
                name="audit_entry_entity__f62798_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="auditentry",
            index=models.Index(
                fields=["action_type"],
                name="audit_entry_action__a0cb4f_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="auditentry",
            index=models.Index(
                fields=["actor_email"],
                name="audit_entry_actor_e_2d9498_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="auditentry",
            index=models.Index(
                fields=["occurred_at"],
                name="audit_entry_occurre_d7e0ca_idx",
            ),
        ),
    ]
