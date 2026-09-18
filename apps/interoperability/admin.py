from django import forms
from django.contrib import admin

from aegis_share.models import CustomUser
from apps.clinical.pep.permissions import is_internal_professional

from .models import LaboratorySource


class LaboratorySourceForm(forms.ModelForm):
    class Meta:
        model = LaboratorySource
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["operators"].queryset = CustomUser.objects.filter(
            nivel_permissao__in=["ADM", "FUNC"]
        )


@admin.register(LaboratorySource)
class LaboratorySourceAdmin(admin.ModelAdmin):
    form = LaboratorySourceForm
    list_display = ["code", "active"]
    list_filter = ["active"]
    filter_horizontal = ["operators"]

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
