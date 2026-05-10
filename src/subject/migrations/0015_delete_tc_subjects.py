from django.db import migrations


def delete_tc_subjects(apps, schema_editor):
    Subject = apps.get_model("subject", "Subject")
    Subject.objects.filter(type="TC").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("subject", "0014_remove_subject_stage"),
    ]

    operations = [
        migrations.RunPython(delete_tc_subjects, migrations.RunPython.noop),
    ]
