from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "auditableEntity",
            "0002_rename_audit_entry_entity__f62798_idx_audit_entry_entity__202b83_idx_and_more",
        ),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="auditentry",
            name="audit_entry_actor_e_270ac8_idx",
        ),
        migrations.RemoveField(
            model_name="auditentry",
            name="actor_email",
        ),
        migrations.AddField(
            model_name="auditentry",
            name="actor_name",
            field=models.CharField(blank=True, default="", max_length=255),
            preserve_default=False,
        ),
        migrations.AddIndex(
            model_name="auditentry",
            index=models.Index(
                fields=["actor_name"],
                name="audit_entry_actor_n_5fe643_idx",
            ),
        ),
    ]
