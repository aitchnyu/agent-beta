from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djangoapp', '0027_notification_recipient_public_id_idx'),
    ]

    operations = [
        migrations.CreateModel(
            name='BackupMarker',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', models.CharField(editable=False, max_length=64, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'get_latest_by': ('created_at', 'pk'),
                'ordering': ('-created_at', '-pk'),
            },
        ),
    ]
