from django.test import TestCase

from aegis_share.models import FileAccess, Workspace, WorkspaceMember

from .helpers import make_file, make_user


class FilePermissionTests(TestCase):
    def setUp(self):
        self.owner = make_user("owner")
        self.other_client = make_user("other")
        self.employee = make_user("employee", role="FUNC")
        self.admin = make_user("admin", role="ADM")
        self.file = make_file(self.owner)

    def test_owner_and_admin_have_access(self):
        self.assertTrue(self.file.user_tem_acesso(self.owner))
        self.assertTrue(self.file.user_tem_acesso(self.admin))

    def test_unrelated_user_has_no_access(self):
        self.assertFalse(self.file.user_tem_acesso(self.other_client))
        self.assertFalse(self.file.user_tem_acesso(self.employee))

    def test_direct_grant_enables_view_but_not_reshare(self):
        FileAccess.objects.create(
            arquivo=self.file,
            user=self.employee,
            granted_by=self.admin,
        )
        self.assertTrue(self.file.user_tem_acesso(self.employee))
        self.assertFalse(self.file.user_pode_compartilhar(self.employee))

    def test_workspace_member_access_and_share_permission(self):
        workspace = Workspace.objects.create(
            name="Cliente A",
            cliente=self.owner,
            created_by=self.admin,
        )
        WorkspaceMember.objects.create(
            workspace=workspace,
            user=self.employee,
            can_upload=True,
            can_share=True,
        )
        self.file.workspace = workspace
        self.file.save(update_fields=["workspace", "updated_at"])

        self.assertTrue(self.file.user_tem_acesso(self.employee))
        self.assertTrue(self.file.user_pode_compartilhar(self.employee))

    def test_soft_delete_removes_access_and_restore_recovers_it(self):
        self.file.soft_delete(self.owner)
        self.file.refresh_from_db()
        self.assertIsNotNone(self.file.deleted_at)
        self.assertFalse(self.file.user_tem_acesso(self.owner))

        self.file.restore()
        self.file.refresh_from_db()
        self.assertIsNone(self.file.deleted_at)
        self.assertTrue(self.file.user_tem_acesso(self.owner))

    def test_only_owner_or_admin_can_modify(self):
        self.assertTrue(self.file.user_pode_alterar(self.owner))
        self.assertTrue(self.file.user_pode_alterar(self.admin))
        self.assertFalse(self.file.user_pode_alterar(self.employee))
        self.assertFalse(self.file.user_pode_alterar(self.other_client))
