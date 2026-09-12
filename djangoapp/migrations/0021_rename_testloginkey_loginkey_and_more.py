# Hand-squashed final state of this session's uncommitted changes: the
# TestLoginKey -> LoginKey rename (as a true RenameModel, preserving rows)
# plus the UserHistory action choices the admin features need. Replaces the
# three intermediate autodetected migrations (add choices, add+rename,
# drop choice) that never shipped anywhere.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djangoapp', '0020_testloginkey'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='TestLoginKey',
            new_name='LoginKey',
        ),
        migrations.AlterField(
            model_name='loginkey',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.RESTRICT, related_name='login_keys', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='userhistory',
            name='action',
            field=models.CharField(choices=[('created', 'Created'), ('edited', 'Edited'), ('deleted', 'Deleted'), ('login', 'Login'), ('login_link', 'Login link')], max_length=20),
        ),
    ]
