from django.db import migrations


def create_teacher_table_if_missing(apps, schema_editor):
    Teacher = apps.get_model("teacher", "Teacher")
    table_name = Teacher._meta.db_table
    existing_tables = schema_editor.connection.introspection.table_names()

    if table_name not in existing_tables:
        schema_editor.create_model(Teacher)


def drop_teacher_table_if_exists(apps, schema_editor):
    Teacher = apps.get_model("teacher", "Teacher")
    table_name = Teacher._meta.db_table
    existing_tables = schema_editor.connection.introspection.table_names()

    if table_name in existing_tables:
        schema_editor.delete_model(Teacher)


class Migration(migrations.Migration):
    dependencies = [
        ("teacher", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            create_teacher_table_if_missing,
            reverse_code=drop_teacher_table_if_exists,
        ),
    ]
