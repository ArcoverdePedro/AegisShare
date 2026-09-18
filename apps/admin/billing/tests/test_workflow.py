import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from auditlog.models import LogEntry
from django.contrib import admin
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, connection
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from aegis_share.tests.helpers import make_user
from apps.clinical.pep.models import Encounter, Patient, PatientAccessGrant
from apps.clinical.pep.tests.test_views import TEST_STORAGES

from ..models import BillingItem, HospitalAccount
from ..services import BillingConflict, add_item, open_account
from ..totals import account_total


@override_settings(STORAGES=TEST_STORAGES, SECURE_SSL_REDIRECT=False)
class BillingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = make_user("billing-admin", role="ADM")
        cls.admin.is_superuser = True
        cls.admin.save(update_fields=["is_superuser"])
        cls.user = make_user("billing-user", role="FUNC")
        cls.other = make_user("billing-other", role="FUNC")
        cls.permissions = Permission.objects.filter(
            content_type__app_label="billing",
            codename__in=["view_accounts", "open_account", "add_item"],
        )
        for user in (cls.user, cls.other):
            user.user_permissions.add(*cls.permissions)
        cls.patient = Patient.objects.create(
            identifier_type="OTHER",
            identifier="BILL-SYNTH",
            full_name="Paciente sintético BILL",
            birth_date=date(1990, 1, 1),
            created_by=cls.user,
        )
        cls.encounter = Encounter.objects.create(
            patient=cls.patient, responsible_professional=cls.user, created_by=cls.user
        )
        cls.url = reverse("billing:account_open", args=[cls.encounter.pk])
        cls.list_url = reverse("billing:account_list")

    def setUp(self):
        self.client.force_login(self.user)

    def account(self):
        return open_account(
            user=self.user,
            encounter_id=self.encounter.pk,
            operation_key=uuid.uuid4(),
            confirmed=True,
        )

    def data(self, **changes):
        return {
            "description": "ITEM-PRIVATE",
            "quantity": 1,
            "unit_price": "0.20",
            "operation_key": uuid.uuid4(),
            "confirmed": True,
            **changes,
        }

    def item(self, account, **changes):
        return add_item(user=self.user, account_id=account.pk, **self.data(**changes))

    def test_open_after_closure_retry_and_single_account(self):
        Encounter.objects.filter(pk=self.encounter.pk).update(status=Encounter.Status.CLOSED)
        data = {"operation_key": uuid.uuid4(), "confirmed": True, "opened_by": self.other.pk}
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)
        account = HospitalAccount.objects.get()
        original_time = account.opened_at
        self.assertEqual(account.opened_by, self.user)
        self.assertEqual(self.client.post(self.url, data).url, response.url)
        self.assertEqual(
            self.client.post(
                self.url, {"operation_key": uuid.uuid4(), "confirmed": True}
            ).status_code,
            409,
        )
        self.assertEqual(self.client.get(self.url).url, response.url)
        account.refresh_from_db()
        self.assertEqual(account.opened_at, original_time)
        self.assertEqual(HospitalAccount.objects.count(), 1)
        self.assertEqual(account_total(account), Decimal("0.00"))
        self.assertEqual(
            self.client.post(
                reverse("billing:item_create", args=[account.pk]), self.data()
            ).status_code,
            302,
        )
        self.encounter.refresh_from_db()
        self.assertEqual(self.encounter.status, Encounter.Status.CLOSED)

    def test_exact_decimal_and_maximum_total_without_integer_overflow(self):
        account = self.account()
        self.item(account, quantity=3, unit_price="0.10")
        self.item(account, quantity=1, unit_price="0.20")
        self.item(account, unit_price="0")
        self.assertEqual(account_total(account), Decimal("0.50"))
        for _ in range(10):
            item = self.item(account, quantity=999999, unit_price="9999999999.99")
            self.assertEqual(item.subtotal, Decimal("999999") * Decimal("9999999999.99"))
        expected = Decimal("0.50") + 10 * Decimal("999999") * Decimal("9999999999.99")
        self.assertEqual(account_total(account), expected)
        for item in account.items.all():
            self.assertEqual(item.subtotal, item.unit_price * item.quantity)

    def test_item_retry_normalizes_decimal_and_trim_and_new_key_is_distinct(self):
        account = self.account()
        url = reverse("billing:item_create", args=[account.pk])
        data = self.data(description=" ITEM-PRIVATE ", unit_price="1")
        self.assertEqual(self.client.post(url, data).status_code, 302)
        item = BillingItem.objects.get()
        original_time = item.recorded_at
        self.assertEqual(
            self.client.post(
                url, {**data, "description": "ITEM-PRIVATE", "unit_price": "1.00"}
            ).status_code,
            302,
        )
        response = self.client.post(url, {**data, "quantity": 2})
        self.assertEqual(response.status_code, 409)
        self.assertNotContains(response, str(item.pk), status_code=409)
        item.refresh_from_db()
        self.assertEqual(
            (item.recorded_at, item.description, item.unit_price),
            (original_time, "ITEM-PRIVATE", Decimal("1.00")),
        )
        self.assertEqual(
            self.client.post(url, {**data, "operation_key": uuid.uuid4()}).status_code, 302
        )
        self.assertEqual(BillingItem.objects.count(), 2)

    def test_invalid_values_and_missing_confirmation_preserve_key(self):
        account = self.account()
        url = reverse("billing:item_create", args=[account.pk])
        for field, values in {
            "quantity": ["1.5", 0, -1, 1000000],
            "unit_price": [
                "-0.01",
                "NaN",
                "Infinity",
                "0.001",
                "10000000000.00",
                "1,50",
                "R$ 1.50",
            ],
            "description": ["  ", "x" * 201],
            "operation_key": ["bad"],
            "confirmed": [False],
        }.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    data = self.data(**{field: value})
                    response = self.client.post(url, data)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(
                        str(response.context["form"]["operation_key"].value()),
                        str(data["operation_key"]),
                    )
        with self.assertRaises(BillingConflict):
            self.item(account, unit_price="NaN")
        self.assertFalse(BillingItem.objects.exists())

    def test_open_confirmation_is_required(self):
        self.assertEqual(
            self.client.post(self.url, {"operation_key": uuid.uuid4()}).status_code, 200
        )
        with self.assertRaises(BillingConflict):
            open_account(
                user=self.user,
                encounter_id=self.encounter.pk,
                operation_key=uuid.uuid4(),
                confirmed=False,
            )
        self.assertFalse(HospitalAccount.objects.exists())

    def test_scope_revocation_and_inactive_patient(self):
        account = self.account()
        detail, create = (
            reverse("billing:account_detail", args=[account.pk]),
            reverse("billing:item_create", args=[account.pk]),
        )
        grant = PatientAccessGrant.objects.create(
            patient=self.patient, user=self.other, granted_by=self.admin, reason="Sintético"
        )
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(create).status_code, 200)
        grant.delete()
        for url in (self.url, detail, create):
            self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(create, self.data()).status_code, 404)
        self.assertNotContains(self.client.get(self.list_url), self.patient.full_name)
        self.client.force_login(self.user)
        self.patient.active = False
        self.patient.save()
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.assertEqual(self.client.post(create, self.data()).status_code, 404)

    def test_capabilities_internal_role_and_admin_without_capability(self):
        account = self.account()
        create = reverse("billing:item_create", args=[account.pk])
        self.user.user_permissions.set(self.permissions.filter(codename="view_accounts"))
        self.assertEqual(self.client.get(self.list_url).status_code, 200)
        self.assertEqual(
            self.client.post(
                self.url, {"operation_key": uuid.uuid4(), "confirmed": True}
            ).status_code,
            403,
        )
        self.assertEqual(self.client.post(create, self.data()).status_code, 403)
        self.user.user_permissions.set(self.permissions.exclude(codename="view_accounts"))
        self.assertEqual(self.client.get(create).status_code, 403)
        outsider = make_user("billing-client", role="CLI")
        outsider.user_permissions.add(*self.permissions)
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(self.list_url).status_code, 403)
        self.admin.is_superuser = False
        self.admin.save(update_fields=["is_superuser"])
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.list_url).status_code, 403)

    def test_conflicting_actor_and_other_account_key_do_not_reveal_original(self):
        account = self.account()
        grant = PatientAccessGrant.objects.create(
            patient=self.patient, user=self.other, granted_by=self.admin, reason="Sintético"
        )
        self.client.force_login(self.other)
        response = self.client.post(
            self.url, {"operation_key": account.operation_key, "confirmed": True}
        )
        self.assertEqual(response.status_code, 409)
        self.assertNotContains(response, str(account.pk), status_code=409)
        grant.delete()
        self.client.force_login(self.user)
        item = self.item(account)
        encounter = Encounter.objects.create(
            patient=self.patient, responsible_professional=self.user, created_by=self.user
        )
        other_account = open_account(
            user=self.user, encounter_id=encounter.pk, operation_key=uuid.uuid4(), confirmed=True
        )
        response = self.client.post(
            reverse("billing:item_create", args=[other_account.pk]),
            self.data(operation_key=item.operation_key),
        )
        self.assertEqual(response.status_code, 409)
        self.assertNotContains(response, str(item.pk), status_code=409)

    def test_audit_failure_rolls_back_account_item_and_blocks_reads(self):
        self.client.get(self.url)
        with patch(
            "auditlog.models.LogEntry.objects.create",
            side_effect=IntegrityError("audit unavailable"),
        ):
            self.assertEqual(
                self.client.post(
                    self.url, {"operation_key": uuid.uuid4(), "confirmed": True}
                ).status_code,
                503,
            )
        self.assertFalse(HospitalAccount.objects.exists())
        account = self.account()
        create, detail = (
            reverse("billing:item_create", args=[account.pk]),
            reverse("billing:account_detail", args=[account.pk]),
        )
        with patch(
            "auditlog.models.LogEntry.objects.create",
            side_effect=IntegrityError("audit unavailable"),
        ):
            self.assertEqual(self.client.post(create, self.data()).status_code, 503)
        self.assertFalse(BillingItem.objects.exists())
        with patch(
            "apps.admin.billing.views.accessed.send", side_effect=DatabaseError("audit unavailable")
        ):
            for url in (self.url, self.list_url, detail, create):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 503)
                self.assertNotContains(response, self.patient.full_name, status_code=503)

    def test_append_only_protection_and_minimized_audit(self):
        account = self.account()
        item = self.item(account, unit_price="37.77")
        for obj in (account, item):
            with self.assertRaises(ValidationError):
                obj.save()
            with self.assertRaises(ValidationError):
                obj.delete()
            self.assertNotIn(type(obj), admin.site._registry)
        with self.assertRaises(ProtectedError):
            self.encounter.delete()
        self.client.get(reverse("billing:account_detail", args=[account.pk]))
        logs = LogEntry.objects.filter(content_type__app_label="billing")
        serialized = str(list(logs.values("changes", "object_repr", "additional_data")))
        for marker in (self.patient.full_name, item.description, "37.77"):
            self.assertNotIn(marker, serialized)
        for obj in (account, item):
            self.assertTrue(
                logs.filter(
                    object_pk=str(obj.pk), action=LogEntry.Action.CREATE, actor=self.user
                ).exists()
            )
            self.assertTrue(
                logs.filter(
                    object_pk=str(obj.pk), action=LogEntry.Action.ACCESS, actor=self.user
                ).exists()
            )

    def test_item_pagination_total_all_rows_and_bounded_queries(self):
        account = self.account()
        for _ in range(26):
            self.item(account)
        LogEntry.objects.filter(
            content_type__app_label="billing", action=LogEntry.Action.ACCESS
        ).delete()
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("billing:account_detail", args=[account.pk]))
        self.assertEqual(len(response.context["page_obj"]), 25)
        self.assertEqual(response.context["total"], Decimal("5.20"))
        self.assertEqual(
            LogEntry.objects.filter(
                content_type__app_label="billing", action=LogEntry.Action.ACCESS
            ).count(),
            26,
        )
        related = [
            q
            for q in queries
            if q["sql"].startswith("SELECT") and '"aegis_share_customuser"' in q["sql"]
        ]
        self.assertLessEqual(len(related), 4)
        self.assertEqual(
            len(
                self.client.get(
                    reverse("billing:account_detail", args=[account.pk]), {"page": 2}
                ).context["page_obj"]
            ),
            1,
        )

    def test_privacy_headers_errors_redirects_csrf_and_methods(self):
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        responses = [
            self.client.get(self.url),
            self.client.put(self.url),
            csrf.post(self.url, {}),
            self.client.get(reverse("billing:account_detail", args=[uuid.uuid4()])),
        ]
        self.client.logout()
        responses.append(self.client.get(self.list_url))
        self.assertEqual([r.status_code for r in responses], [200, 405, 403, 404, 302])
        for response in responses:
            self.assertEqual(response["Cache-Control"], "private, no-store")
            self.assertIn("Cookie", response["Vary"])
            self.assertEqual(response["X-Content-Type-Options"], "nosniff")
