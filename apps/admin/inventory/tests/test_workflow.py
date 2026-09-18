import uuid
from unittest.mock import patch

from auditlog.models import LogEntry
from django.contrib import admin
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, connection
from django.db.models.deletion import ProtectedError
from django.test import Client, RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from aegis_share.tests.helpers import make_user
from apps.clinical.pep.tests.test_views import TEST_STORAGES
from apps.clinical.prescription.models import StockItem, StockMovement

from ..models import InventoryItem, Requisition
from ..services import InventoryConflict, request_material


@override_settings(STORAGES=TEST_STORAGES, SECURE_SSL_REDIRECT=False)
class InventoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = make_user("inventory-admin", role="ADM")
        cls.admin.is_superuser = cls.admin.is_staff = True
        cls.admin.save(update_fields=["is_superuser", "is_staff"])
        cls.user = make_user("inventory-user", role="FUNC")
        cls.other = make_user("inventory-other", role="FUNC")
        cls.permissions = Permission.objects.filter(
            content_type__app_label="inventory",
            codename__in=["view_requisitions", "request_material"],
        )
        for user in (cls.user, cls.other):
            user.user_permissions.add(*cls.permissions)
        cls.material = InventoryItem.objects.create(
            code="INV-PRIVATE", name="Material sintético", unit="caixa"
        )
        cls.url = reverse("inventory:requisition_create")
        cls.list_url = reverse("inventory:requisition_list")
        cls.catalog_url = reverse("inventory:item_list")

    def setUp(self):
        self.client.force_login(self.user)

    def data(self, **changes):
        return {
            "item": self.material.pk,
            "quantity": 3,
            "operation_key": uuid.uuid4(),
            "confirmed": True,
            **changes,
        }

    def order(self, **changes):
        return request_material(
            user=self.user,
            item=self.material,
            quantity=3,
            operation_key=changes.get("operation_key", uuid.uuid4()),
            confirmed=True,
        )

    def test_snapshot_retry_inactive_and_new_key(self):
        data = self.data(item_name="FORGED", item_unit="FORGED", requested_by=self.other.pk)
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)
        item = Requisition.objects.get()
        original = item.requested_at
        self.assertEqual(
            (item.item_code, item.item_name, item.item_unit, item.requested_by_id),
            (self.material.code, self.material.name, self.material.unit, self.user.pk),
        )
        self.material.code, self.material.name, self.material.unit, self.material.active = (
            "Changed",
            "Changed",
            "unidade",
            False,
        )
        self.material.save()
        self.assertEqual(self.client.post(self.url, data).url, response.url)
        item.refresh_from_db()
        self.assertEqual(
            (item.requested_at, item.item_name, item.item_unit),
            (original, "Material sintético", "caixa"),
        )
        self.assertEqual(self.client.post(self.url, self.data()).status_code, 409)
        self.assertNotContains(self.client.get(self.catalog_url), "Changed")
        self.assertNotContains(self.client.get(self.url), "Changed")
        self.assertContains(self.client.get(response.url), "Material sintético")
        self.material.active = True
        self.material.save()
        self.assertEqual(self.client.post(self.url, self.data()).status_code, 302)
        self.assertEqual(Requisition.objects.count(), 2)
        self.assertFalse(StockItem.objects.exists())
        self.assertFalse(StockMovement.objects.exists())

    def test_institutional_read_and_capability_revocation(self):
        item = self.order()
        self.client.force_login(self.other)
        self.assertContains(self.client.get(self.list_url), self.material.name)
        self.assertEqual(
            self.client.get(reverse("inventory:requisition_detail", args=[item.pk])).status_code,
            200,
        )
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.other.user_permissions.remove(*self.permissions.filter(codename="request_material"))
        self.assertEqual(self.client.post(self.url, self.data()).status_code, 403)
        self.assertEqual(self.client.get(self.list_url).status_code, 200)
        self.other.user_permissions.clear()
        self.assertEqual(self.client.get(self.catalog_url).status_code, 403)
        self.assertEqual(Requisition.objects.count(), 1)

    def test_internal_role_and_both_capabilities_required(self):
        self.user.user_permissions.set(self.permissions.filter(codename="request_material"))
        self.assertEqual(self.client.post(self.url, self.data()).status_code, 403)
        outsider = make_user("inventory-client", role="CLI")
        outsider.user_permissions.add(*self.permissions)
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(self.list_url).status_code, 403)
        self.assertEqual(self.client.post(self.url, self.data()).status_code, 403)
        self.admin.is_superuser = False
        self.admin.save(update_fields=["is_superuser"])
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.catalog_url).status_code, 403)

    def test_invalid_input_preserves_key_and_internal_validation(self):
        for changes in (
            {"quantity": 0},
            {"quantity": -1},
            {"quantity": "1.5"},
            {"quantity": 1000000},
            {"quantity": "NaN"},
            {"confirmed": False},
            {"operation_key": "bad"},
            {"item": uuid.uuid4()},
        ):
            with self.subTest(changes=changes):
                data = self.data(**changes)
                response = self.client.post(self.url, data)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    str(response.context["form"]["operation_key"].value()),
                    str(data["operation_key"]),
                )
        self.assertFalse(Requisition.objects.exists())
        with self.assertRaises(InventoryConflict):
            request_material(
                user=self.user,
                item=self.material,
                quantity="1.5",
                operation_key=uuid.uuid4(),
                confirmed=True,
            )
        for quantity in (1, 999999):
            self.assertEqual(
                self.client.post(self.url, self.data(quantity=quantity)).status_code, 302
            )

    def test_conflicts_do_not_reveal_original(self):
        item = self.order()
        other = InventoryItem.objects.create(code="OTHER", name="Other", unit="unidade")
        for changes in ({"quantity": 4}, {"item": other.pk}):
            response = self.client.post(
                self.url, self.data(operation_key=item.operation_key, **changes)
            )
            self.assertEqual(response.status_code, 409)
            self.assertNotContains(response, str(item.pk), status_code=409)
        self.client.force_login(self.other)
        self.assertEqual(
            self.client.post(self.url, self.data(operation_key=item.operation_key)).status_code, 409
        )
        self.assertEqual(Requisition.objects.count(), 1)

    def test_audit_failure_rolls_back_and_blocks_reads_and_retries(self):
        self.client.get(self.url)
        with patch(
            "auditlog.models.LogEntry.objects.create",
            side_effect=IntegrityError("audit unavailable"),
        ):
            self.assertEqual(self.client.post(self.url, self.data()).status_code, 503)
        self.assertFalse(Requisition.objects.exists())
        item = self.order()
        with patch(
            "apps.admin.inventory.views.accessed.send",
            side_effect=DatabaseError("audit unavailable"),
        ):
            for url in (
                self.url,
                self.catalog_url,
                self.list_url,
                reverse("inventory:requisition_detail", args=[item.pk]),
            ):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 503)
                self.assertNotContains(response, self.material.name, status_code=503)
        with patch(
            "apps.admin.inventory.services.accessed.send",
            side_effect=DatabaseError("audit unavailable"),
        ):
            self.assertEqual(
                self.client.post(self.url, self.data(operation_key=item.operation_key)).status_code,
                503,
            )
        with patch(
            "apps.admin.inventory.services.Requisition.objects.create",
            side_effect=IntegrityError("other constraint"),
        ):
            self.assertEqual(self.client.post(self.url, self.data()).status_code, 503)
        self.assertEqual(Requisition.objects.count(), 1)

    def test_catalog_validation_admin_and_append_only_protection(self):
        item = self.order()
        with self.assertRaises(ValidationError):
            item.save()
        with self.assertRaises(ValidationError):
            item.delete()
        with self.assertRaises(ProtectedError):
            self.material.delete()
        for field in ("code", "name", "unit"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                InventoryItem.objects.create(
                    **{"code": "VALID", "name": "Valid", "unit": "unidade", field: "   "}
                )
        catalog = InventoryItem.objects.create(code=" trimmed ", name=" Name ", unit=" caixa ")
        self.assertEqual((catalog.code, catalog.name, catalog.unit), ("trimmed", "Name", "caixa"))
        with self.assertRaises(ValidationError):
            InventoryItem.objects.create(code="trimmed", name="Other", unit="unidade")
        self.assertNotIn(Requisition, admin.site._registry)
        request = RequestFactory().get("/")
        request.user = make_user("inventory-client-admin", role="CLI")
        request.user.is_superuser = request.user.is_staff = True
        self.assertFalse(admin.site._registry[InventoryItem].has_change_permission(request))
        request.user = self.admin
        self.assertTrue(admin.site._registry[InventoryItem].has_change_permission(request))

    def test_minimized_audit_and_exact_rendered_form_choices(self):
        inactive = InventoryItem.objects.create(
            code="INACTIVE", name="Inactive", unit="unidade", active=False
        )
        item = self.order()
        LogEntry.objects.filter(
            content_type__app_label="inventory", action=LogEntry.Action.ACCESS
        ).delete()
        self.client.get(self.url)
        accesses = LogEntry.objects.filter(
            content_type__app_label="inventory", action=LogEntry.Action.ACCESS
        )
        self.assertEqual(
            list(accesses.values_list("object_pk", flat=True)), [str(self.material.pk)]
        )
        self.assertFalse(accesses.filter(object_pk=str(inactive.pk)).exists())
        self.client.get(reverse("inventory:requisition_detail", args=[item.pk]))
        logs = LogEntry.objects.filter(content_type__app_label="inventory")
        serialized = str(list(logs.values("changes", "object_repr", "additional_data")))
        for marker in (self.material.code, self.material.name, '"quantity"', '"item_unit"'):
            self.assertNotIn(marker, serialized)
        for action in (LogEntry.Action.CREATE, LogEntry.Action.ACCESS):
            self.assertTrue(
                logs.filter(object_pk=str(item.pk), action=action, actor=self.user).exists()
            )

    def test_pagination_audits_only_page_and_no_related_n_plus_one(self):
        for _ in range(26):
            self.order()
        for index in range(25):
            InventoryItem.objects.create(code=f"PAGE-{index:02}", name="Synthetic", unit="unidade")
        for url in (self.list_url, self.catalog_url):
            LogEntry.objects.filter(
                content_type__app_label="inventory", action=LogEntry.Action.ACCESS
            ).delete()
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get(url)
            self.assertEqual(len(response.context["page_obj"]), 25)
            self.assertEqual(
                LogEntry.objects.filter(
                    content_type__app_label="inventory", action=LogEntry.Action.ACCESS
                ).count(),
                25,
            )
            related = [
                q
                for q in queries
                if q["sql"].startswith("SELECT") and '"aegis_share_customuser"' in q["sql"]
            ]
            self.assertLessEqual(len(related), 3)
            self.assertEqual(len(self.client.get(url, {"page": 2}).context["page_obj"]), 1)

    def test_privacy_headers_csrf_methods_missing_and_redirects(self):
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        responses = [
            self.client.get(self.url),
            self.client.put(self.url),
            csrf.post(self.url, self.data()),
            self.client.get(reverse("inventory:requisition_detail", args=[uuid.uuid4()])),
        ]
        self.client.logout()
        responses.append(self.client.get(self.catalog_url))
        self.assertEqual([r.status_code for r in responses], [200, 405, 403, 404, 302])
        for response in responses:
            self.assertEqual(response["Cache-Control"], "private, no-store")
            self.assertIn("Cookie", response["Vary"])
            self.assertEqual(response["X-Content-Type-Options"], "nosniff")
