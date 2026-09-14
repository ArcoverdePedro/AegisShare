import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PushSubscription",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("endpoint", models.TextField()),
                ("endpoint_hash", models.CharField(editable=False, max_length=64, unique=True)),
                (
                    "session_fingerprint",
                    models.CharField(db_index=True, editable=False, max_length=64),
                ),
                ("p256dh", models.TextField()),
                ("auth", models.TextField()),
                ("active", models.BooleanField(db_index=True, default=True)),
                ("failure_count", models.PositiveIntegerField(default=0)),
                ("last_success_at", models.DateTimeField(blank=True, null=True)),
                ("disabled_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="push_subscriptions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-updated_at"],
            },
        ),
        migrations.AddIndex(
            model_name="pushsubscription",
            index=models.Index(
                fields=["user", "active"],
                name="pwa_push_user_active_idx",
            ),
        ),
    ]
