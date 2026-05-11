"""Data migration: uppercase existing group stage values."""

from django.db import migrations

STAGE_MAP = {
    "preschool": "PRESCHOOL",
    "primary": "PRIMARY",
    "secondary": "SECONDARY",
    "alevels": "ALEVELS",
}


def uppercase_stages(apps, schema_editor):
    Group = apps.get_model("group", "Group")
    for group in Group.objects.all():
        mapped = STAGE_MAP.get(group.stage)
        if mapped and mapped != group.stage:
            Group.objects.filter(pk=group.pk).update(stage=mapped)


def reverse_uppercase_stages(apps, schema_editor):
    pass  # not reversible


class Migration(migrations.Migration):
    dependencies = [
        ("group", "0005_alter_group_stage"),
    ]

    operations = [
        migrations.RunPython(uppercase_stages, reverse_uppercase_stages),
    ]
