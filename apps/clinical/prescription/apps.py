from django.apps import AppConfig


class PrescriptionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.clinical.prescription"
    label = "prescription"
    verbose_name = "Prescrição e Farmácia"

    def ready(self):
        from . import signals  # noqa: F401
