from django.contrib import admin

from .models import (
    Admission,
    Bed,
    BedOccupancy,
    Discharge,
    Location,
    Transfer,
    UserLocationAccess,
)


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "kind", "active", "parent")
    list_filter = ("kind", "active")
    search_fields = ("code", "name")


@admin.register(Bed)
class BedAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "location", "operational_status", "active")
    list_filter = ("operational_status", "active", "location")
    search_fields = ("code", "label", "location__name", "location__code")


@admin.register(UserLocationAccess)
class UserLocationAccessAdmin(admin.ModelAdmin):
    list_display = ("user", "location", "granted_by", "created_at")
    list_filter = ("location",)
    search_fields = ("user__username", "location__code", "location__name")


@admin.register(Admission)
class AdmissionAdmin(admin.ModelAdmin):
    list_display = ("id", "encounter", "admitted_at", "admitted_by")
    readonly_fields = ("operation_key", "created_at")


@admin.register(BedOccupancy)
class BedOccupancyAdmin(admin.ModelAdmin):
    list_display = ("id", "bed", "admission", "started_at", "ended_at")
    list_filter = ("end_reason", "bed__location")


class ImmutableLifecycleAdmin(admin.ModelAdmin):
    """Permite inspeção administrativa sem editar ou apagar histórico concluído."""

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Transfer)
class TransferAdmin(ImmutableLifecycleAdmin):
    list_display = (
        "id",
        "admission",
        "source_occupancy",
        "destination_occupancy",
        "transferred_at",
        "transferred_by",
    )
    list_filter = ("transferred_at",)


@admin.register(Discharge)
class DischargeAdmin(ImmutableLifecycleAdmin):
    list_display = (
        "id",
        "admission",
        "discharged_at",
        "disposition",
        "discharged_by",
    )
    list_filter = ("disposition", "discharged_at")
