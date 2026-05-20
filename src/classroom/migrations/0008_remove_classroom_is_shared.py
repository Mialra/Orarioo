from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("classroom", "0007_remove_classroom_classroom_name_ci_unique_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="classroom",
            name="is_shared",
        ),
    ]
