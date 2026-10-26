import csv
from datetime import date, timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from aegis_share.tests.helpers import make_user
from apps.clinical.pep.models import Patient, PatientAccessGrant


class AccessReviewTests(TestCase):
    def test_exports_current_grants_without_patient_names(self):
        admin = make_user("review-admin", role="ADM")
        nurse = make_user("review-nurse", role="FUNC")
        nurse.user_permissions.add(Permission.objects.get(codename="view_requests"))
        patient = Patient.objects.create(
            identifier_type="OTHER",
            identifier="REV-1",
            full_name="Nome Secreto",
            birth_date=date(1990, 1, 1),
            created_by=admin,
        )
        PatientAccessGrant.objects.create(patient=patient, user=nurse, reason="x", granted_by=admin)
        PatientAccessGrant.objects.create(
            patient=patient,
            user=admin,
            reason="y",
            granted_by=admin,
            expires_at=timezone.now() - timedelta(days=1),
        )
        out = StringIO()

        with patch("sys.stdout", out):
            call_command("access_review")

        rows = list(csv.DictReader(StringIO(out.getvalue())))
        self.assertNotIn("Nome Secreto", out.getvalue())
        self.assertIn(
            ("review-nurse", "PACIENTE", str(patient.pk)),
            {(r["usuario"], r["tipo"], r["objeto"]) for r in rows},
        )
        self.assertIn(
            ("review-nurse", "PERMISSAO", "compliance.view_requests"),
            {(r["usuario"], r["tipo"], r["objeto"]) for r in rows},
        )
        self.assertFalse(
            [r for r in rows if r["usuario"] == "review-admin" and r["tipo"] == "PACIENTE"]
        )
