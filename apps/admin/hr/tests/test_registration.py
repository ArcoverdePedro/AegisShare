from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from aegis_share.tests.helpers import make_user

from ..models import Employee, EmployeeAbsence, absent_on


class RegistrationTests(TestCase):
    def test_registration_requires_council_and_state_and_absence_period_is_valid(self):
        user = make_user("hr-reg", role="FUNC")
        employee = Employee(user=user, department="UTI", job_title="Enfermeira")
        employee.registration_number = "12345"
        with self.assertRaises(ValidationError):
            employee.save()
        employee.council, employee.registration_state = "coren", "pe"
        employee.save()
        self.assertEqual((employee.council, employee.registration_state), ("COREN", "PE"))

        EmployeeAbsence.objects.create(
            employee=employee, kind="LEAVE", starts_on="2027-01-10", ends_on="2027-01-12"
        )
        self.assertTrue(absent_on(user, "2027-01-11"))
        self.assertFalse(absent_on(user, "2027-01-13"))
        with self.assertRaises(IntegrityError):
            EmployeeAbsence.objects.create(
                employee=employee, kind="LEAVE", starts_on="2027-01-10", ends_on="2027-01-09"
            )
