from django.contrib import admin

from apps.clinical.pep.permissions import is_internal_professional

from .models import LabTest


@admin.register(LabTest)
class LabTestAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "specimen_type", "active"]
    list_filter = ["active"]
    search_fields = ["code", "name"]

    def has_view_permission(self, request, obj=None):
        return is_internal_professional(request.user) and super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        return is_internal_professional(request.user) and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return is_internal_professional(request.user) and super().has_change_permission(
            request, obj
        )

    def has_delete_permission(self, request, obj=None):
        return is_internal_professional(request.user) and super().has_delete_permission(
            request, obj
        )
