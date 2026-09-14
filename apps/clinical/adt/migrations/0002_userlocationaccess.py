import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("adt", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserLocationAccess",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "granted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="adt_location_accesses_granted",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "location",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="user_accesses",
                        to="adt.location",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="adt_location_accesses",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="userlocationaccess",
            constraint=models.UniqueConstraint(
                fields=("user", "location"),
                name="uniq_adt_user_location_access",
            ),
        ),
        migrations.AddIndex(
            model_name="userlocationaccess",
            index=models.Index(
                fields=["user", "location"],
                name="adt_user_location_idx",
            ),
        ),
    ]
