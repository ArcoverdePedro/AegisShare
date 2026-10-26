from io import StringIO

from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase

from aegis_share.management.commands.sync_role_groups import PREFIX, ROLE_MATRIX
from aegis_share.tests.helpers import make_user


class RoleGroupTests(TestCase):
    def test_dry_run_by_default_and_apply_is_idempotent_without_users(self):
        user = make_user("role-user", role="FUNC")
        call_command("sync_role_groups", stdout=StringIO())
        self.assertFalse(Group.objects.filter(name__startswith=PREFIX).exists())

        call_command("sync_role_groups", "--apply", stdout=StringIO())
        call_command("sync_role_groups", "--apply", stdout=StringIO())

        self.assertEqual(Group.objects.filter(name__startswith=PREFIX).count(), len(ROLE_MATRIX))
        self.assertFalse(user.groups.exists())

    def test_segregation_of_purchase_duties(self):
        for role, names in ROLE_MATRIX.items():
            with self.subTest(role=role):
                self.assertFalse(
                    {"inventory.request_purchase", "inventory.approve_purchase"} <= set(names)
                )
