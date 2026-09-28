from auditlog.context import set_actor
from django.contrib import admin
from django.db import DatabaseError, transaction
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables

from apps.clinical.pep.permissions import is_internal_professional

from .forms import EmployeeAdminForm
from .models import Employee


def _failed():
    return HttpResponse(
        "Não foi possível concluir a operação. Consulte o histórico e tente novamente.",
        status=503,
        content_type="text/plain; charset=utf-8",
    )


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    form = EmployeeAdminForm
    list_display = ["username", "department", "job_title", "active"]
    list_filter = ["active"]
    list_per_page = 25
    list_select_related = ["user"]
    search_fields = ["user__username", "user__first_name", "user__last_name"]
    fields = ["user", "department", "job_title", "active"]

    @admin.display(description="Usuário", ordering="user__username")
    def username(self, obj):
        return obj.user.username

    def get_fields(self, request, obj=None):
        if obj:
            return ["username", "department", "job_title", "active"]
        return self.fields

    def get_readonly_fields(self, request, obj=None):
        return ["username"] if obj else []

    def has_view_permission(self, request, obj=None):
        return is_internal_professional(request.user) and request.user.has_perm("hr.view_employee")

    def has_add_permission(self, request):
        return self.has_view_permission(request) and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_view_permission(request, obj) and super().has_change_permission(
            request, obj
        )

    def has_delete_permission(self, request, obj=None):
        return False

    @method_decorator(sensitive_post_parameters())
    @method_decorator(sensitive_variables())
    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        try:
            with transaction.atomic(), set_actor(request.user):
                return super().changeform_view(request, object_id, form_url, extra_context)
        except DatabaseError:
            return _failed()
