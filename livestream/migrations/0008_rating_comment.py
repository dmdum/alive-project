# Generated by Django 2.0.5 on 2018-06-07 17:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('livestream', '0007_notification_icon'),
    ]

    operations = [
        migrations.AddField(
            model_name='rating',
            name='comment',
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
