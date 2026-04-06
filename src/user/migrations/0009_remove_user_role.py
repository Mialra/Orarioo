from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("user", "0008_rename_collaboratio_invited_6d621a_idx_collaborati_invited_a2b039_idx_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="user",
            name="role",
        ),
    ]
