# Generated by Django 4.2 on 2023-04-03 19:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0003_alter_user_username'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='username',
            field=models.CharField(blank=True, default='dot', max_length=200, unique=True),
            preserve_default=False,
        ),
    ]
