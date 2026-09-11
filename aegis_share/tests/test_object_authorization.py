from django.test import TestCase
from django.urls import reverse

from aegis_share.forms import FolderForm, IPFSForm
from aegis_share.models import (
    Conversation,
    FileAccess,
    Folder,
    SharedLink,
    Workspace,
    WorkspaceMember,
)
from aegis_share.services.files import _validate_upload_scope
from aegis_share.services.selectors import get_accessible_file

from .helpers import make_file, make_user


class CoreObjectAuthorizationTests(TestCase):
    def setUp(self):
        self.owner = make_user("auth-owner")
        self.other_client = make_user("auth-other-client")
        self.employee = make_user("auth-employee", role="FUNC")
        self.intruder = make_user("auth-intruder", role="FUNC")
        self.admin = make_user("auth-admin", role="ADM")
        self.workspace = Workspace.objects.create(
            name="Workspace autorizado",
            cliente=self.owner,
            created_by=self.admin,
        )

    def test_workspace_member_without_upload_permission_is_not_selectable(self):
        WorkspaceMember.objects.create(
            workspace=self.workspace,
            user=self.employee,
            can_upload=False,
            can_share=False,
        )

        upload_form = IPFSForm(user=self.employee)
        folder_form = FolderForm(user=self.employee)

        self.assertFalse(
            upload_form.fields["workspace"].queryset.filter(id=self.workspace.id).exists()
        )
        self.assertFalse(
            folder_form.fields["workspace"].queryset.filter(id=self.workspace.id).exists()
        )

    def test_upload_scope_rejects_workspace_from_another_client(self):
        with self.assertRaisesMessage(
            PermissionError,
            "O workspace nao pertence ao cliente selecionado.",
        ):
            _validate_upload_scope(
                owner=self.other_client,
                actor=self.admin,
                workspace=self.workspace,
            )

    def test_upload_scope_rejects_member_without_upload_permission(self):
        WorkspaceMember.objects.create(
            workspace=self.workspace,
            user=self.employee,
            can_upload=False,
        )

        with self.assertRaisesMessage(
            PermissionError,
            "Usuario sem permissao de upload neste workspace.",
        ):
            _validate_upload_scope(
                owner=self.owner,
                actor=self.employee,
                workspace=self.workspace,
            )

    def test_upload_scope_rejects_folder_from_another_workspace(self):
        WorkspaceMember.objects.create(
            workspace=self.workspace,
            user=self.employee,
            can_upload=True,
        )
        other_workspace = Workspace.objects.create(
            name="Outro workspace",
            cliente=self.owner,
            created_by=self.admin,
        )
        foreign_folder = Folder.objects.create(
            workspace=other_workspace,
            name="Pasta externa",
            created_by=self.admin,
        )

        with self.assertRaisesMessage(
            PermissionError,
            "A pasta nao pertence ao workspace selecionado.",
        ):
            _validate_upload_scope(
                owner=self.owner,
                actor=self.employee,
                workspace=self.workspace,
                folder=foreign_folder,
            )

    def test_deleted_shared_file_is_visible_only_to_owner_in_trash(self):
        file = make_file(self.owner, cid="bafy-auth-trash")
        FileAccess.objects.create(
            arquivo=file,
            user=self.employee,
            granted_by=self.admin,
        )
        file.soft_delete(self.owner)

        self.assertIsNotNone(
            get_accessible_file(self.owner, file.id, include_deleted=True)
        )
        self.assertIsNone(
            get_accessible_file(self.employee, file.id, include_deleted=True)
        )

    def test_chat_index_hides_file_conversation_after_access_revocation(self):
        file = make_file(self.owner, cid="bafy-auth-chat")
        grant = FileAccess.objects.create(
            arquivo=file,
            user=self.employee,
            granted_by=self.admin,
        )
        conversation = Conversation.objects.create(file=file)
        conversation.participants.add(self.owner, self.employee)
        grant.delete()
        self.client.force_login(self.employee)

        response = self.client.get(reverse("chat_index"))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(conversation, list(response.context["conversations"]))

    def test_unrelated_user_cannot_revoke_shared_link(self):
        file = make_file(self.owner, cid="bafy-auth-link")
        link = SharedLink.objects.create(
            file=file,
            token_prefix="auth-link",
            token_hash="a" * 64,
            created_by=self.owner,
        )
        self.client.force_login(self.intruder)

        response = self.client.post(reverse("revoke_file_link", args=[link.id]))

        self.assertEqual(response.status_code, 404)
        link.refresh_from_db()
        self.assertIsNone(link.revoked_at)

    def test_client_cannot_query_user_search_endpoints(self):
        self.client.force_login(self.owner)

        client_response = self.client.get(reverse("buscar_cliente"), {"term": "auth"})
        employee_response = self.client.get(
            reverse("buscar_funcionario"), {"term": "auth"}
        )

        self.assertEqual(client_response.status_code, 403)
        self.assertEqual(employee_response.status_code, 403)
