from django.contrib import admin

from .models import Patient, PatientAccessGrant


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "identifier_type", "birth_date", "active", "created_at")
    list_filter = ("identifier_type", "sex", "active")
    search_fields = ("full_name", "identifier")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(PatientAccessGrant)
class PatientAccessGrantAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "user", "granted_by", "expires_at", "created_at")
    search_fields = ("user__username", "granted_by__username")
    readonly_fields = ("id", "created_at")
