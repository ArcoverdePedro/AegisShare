from django.contrib import admin, messages

from .catalog_services import (
    set_dose_rule_reference_active,
    set_interaction_reference_active,
)
from .models import DoseRule, Interaction
from .permissions import can_manage_reference_data


class GovernedReferenceAdmin(admin.ModelAdmin):
    actions = ("activate_selected", "deactivate_selected")
    readonly_fields = ("active", "approved_by", "approved_at", "created_at", "updated_at")

    def has_module_permission(self, request):
        return can_manage_reference_data(request.user)

    def has_view_permission(self, request, obj=None):
        return can_manage_reference_data(request.user)

    def has_add_permission(self, request):
        return can_manage_reference_data(request.user)

    def has_change_permission(self, request, obj=None):
        return can_manage_reference_data(request.user)

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.active:
            fields.extend(self.governed_fields)
        return tuple(dict.fromkeys(fields))

    @admin.action(description="Ativar referências selecionadas com aprovação do usuário atual")
    def activate_selected(self, request, queryset):
        count = 0
        for obj in queryset:
            self.set_reference_active(obj=obj, actor=request.user, active=True)
            count += 1
        self.message_user(
            request,
            f"{count} referência(s) ativada(s) com aprovação registrada.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Desativar referências selecionadas")
    def deactivate_selected(self, request, queryset):
        count = 0
        for obj in queryset:
            self.set_reference_active(obj=obj, actor=request.user, active=False)
            count += 1
        self.message_user(
            request,
            f"{count} referência(s) desativada(s).",
            level=messages.SUCCESS,
        )


@admin.register(Interaction)
class InteractionAdmin(GovernedReferenceAdmin):
    list_display = (
        "drug_a",
        "drug_b",
        "severity",
        "blocking",
        "reference_version",
        "active",
    )
    list_filter = ("active", "severity", "blocking")
    search_fields = (
        "drug_a__code",
        "drug_a__name",
        "drug_b__code",
        "drug_b__name",
        "reference_source",
        "reference_version",
    )
    governed_fields = (
        "drug_a",
        "drug_b",
        "severity",
        "blocking",
        "summary",
        "reference_source",
        "reference_version",
    )

    def set_reference_active(self, *, obj, actor, active):
        return set_interaction_reference_active(
            interaction_id=obj.pk,
            actor=actor,
            active=active,
        )


@admin.register(DoseRule)
class DoseRuleAdmin(GovernedReferenceAdmin):
    list_display = (
        "rule_code",
        "drug",
        "basis",
        "reference_version",
        "active",
    )
    list_filter = ("active", "basis", "per_kg")
    search_fields = (
        "rule_code",
        "drug__code",
        "drug__name",
        "reference_source",
        "reference_version",
    )
    governed_fields = (
        "drug",
        "rule_code",
        "basis",
        "min_age_days",
        "max_age_days",
        "min_weight_kg",
        "max_weight_kg",
        "min_dose",
        "max_dose",
        "dose_unit",
        "per_kg",
        "reference_source",
        "reference_version",
    )

    def set_reference_active(self, *, obj, actor, active):
        return set_dose_rule_reference_active(
            rule_id=obj.pk,
            actor=actor,
            active=active,
        )
