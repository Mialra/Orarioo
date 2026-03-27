from django.db import migrations, models


def migrate_director_to_direccion(apps, schema_editor):
    User = apps.get_model("user", "User")
    User.objects.filter(role="director").update(role="direccion")


def migrate_direccion_to_director(apps, schema_editor):
    User = apps.get_model("user", "User")
    User.objects.filter(role="direccion").update(role="director")


class Migration(migrations.Migration):

    dependencies = [
        ("user", "0002_user_name_from_namedentity"),
    ]

    operations = [
        migrations.RunPython(
            migrate_director_to_direccion,
            migrate_direccion_to_director,
        ),
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("administrator", "Administrator"),
                    ("direccion", "Direccion"),
                ],
                default="direccion",
                help_text="User role in the system",
                max_length=20,
            ),
        ),
    ]
