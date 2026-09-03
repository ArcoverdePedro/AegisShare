from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    APIToken,
    CustomUser,
    DocumentRequest,
    DocumentRequestItem,
    FileAccess,
    FileComment,
    FileVersion,
    Folder,
    IPFSFile,
    Notification,
    SharedLink,
    Tag,
    TrackedSession,
    UserSecuritySettings,
    Workspace,
    WorkspaceMember,
)


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ("username", "email", "nivel_permissao", "is_staff", "is_active")
    list_filter = ("nivel_permissao", "is_staff", "is_active")
    fieldsets = (
        *UserAdmin.fieldsets,
        ("AegisShare", {"fields": ("telefone", "nivel_permissao", "foto_perfil")}),
    )
    add_fieldsets = (
        *UserAdmin.add_fieldsets,
        ("AegisShare", {"fields": ("email", "telefone", "nivel_permissao")}),
    )
    search_fields = ("username", "email", "telefone")
    ordering = ("username",)


class FileVersionInline(admin.TabularInline):
    model = FileVersion
    extra = 0
    readonly_fields = (
        "id",
        "version_number",
        "cid",
        "pinata_id",
        "sha256",
        "encrypted_sha256",
        "is_encrypted",
        "uploaded_by",
        "created_at",
    )
    exclude = ("wrapped_key",)
    can_delete = False


@admin.register(IPFSFile)
class IPFSFileAdmin(admin.ModelAdmin):
    list_display = (
        "nome_arquivo",
        "dono_arquivo",
        "mime_type",
        "tamanho_arquivo",
        "is_encrypted",
        "data_adicionado",
        "deleted_at",
    )
    list_filter = ("is_encrypted", "mime_type", "deleted_at")
    search_fields = ("nome_arquivo", "cid", "sha256", "dono_arquivo__username")
    readonly_fields = ("cid", "pinata_id", "sha256", "data_adicionado", "updated_at")
    inlines = [FileVersionInline]


@admin.register(FileVersion)
class FileVersionAdmin(admin.ModelAdmin):
    list_display = (
        "file",
        "version_number",
        "is_encrypted",
        "original_size",
        "uploaded_by",
        "created_at",
    )
    search_fields = ("file__nome_arquivo", "cid", "sha256")
    readonly_fields = ("wrapped_key",)


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ("name", "cliente", "created_by", "created_at")
    search_fields = ("name", "cliente__username")


admin.site.register(WorkspaceMember)
admin.site.register(Folder)
admin.site.register(Tag)
admin.site.register(FileAccess)
admin.site.register(SharedLink)
admin.site.register(FileComment)
admin.site.register(DocumentRequest)
admin.site.register(DocumentRequestItem)
admin.site.register(Notification)
admin.site.register(UserSecuritySettings)
admin.site.register(TrackedSession)
admin.site.register(APIToken)
