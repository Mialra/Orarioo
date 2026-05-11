import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auditableEntity", "0003_auditentry_team"),
        ("user", "0007_collaborationteaminvitation"),
    ]

    operations = [
        migrations.AlterField(
            model_name="auditentry",
            name="team",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="audit_entries",
                to="user.collaborationteam",
            ),
        ),
    ]
