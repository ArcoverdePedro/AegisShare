from django.apps import AppConfig


class PepConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.clinical.pep"
    verbose_name = "PEP — Prontuário Eletrônico"
