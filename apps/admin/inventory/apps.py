from django.apps import AppConfig


class InventoryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.admin.inventory"
    verbose_name = "Materiais e requisições"
