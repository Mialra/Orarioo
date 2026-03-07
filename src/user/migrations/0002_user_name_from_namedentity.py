from django.db import migrations, models


def copy_given_name_to_name(apps, schema_editor):
    User = apps.get_model("user", "User")
    for user in User.objects.all():
        if not user.name:
            user.name = user.given_name
            user.save(update_fields=["name"])


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="name",
            field=models.CharField(default="", max_length=150),
            preserve_default=False,
        ),
        migrations.RunPython(copy_given_name_to_name, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="user",
            name="given_name",
        ),
    ]
