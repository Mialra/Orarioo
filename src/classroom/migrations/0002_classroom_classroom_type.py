from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classroom', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='classroom',
            name='classroom_type',
            field=models.CharField(blank=True, default='', max_length=150),
        ),
    ]
