from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("user", "0013_user_deleted_at_and_nullable_password"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="userdataexportlog",
            name="ip_address",
        ),
    ]
