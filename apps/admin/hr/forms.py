from django import forms
from django.contrib.auth import get_user_model

from .models import Employee


class EmployeeAdminForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ["user", "department", "job_title", "active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance._state.adding:
            self.fields["user"].queryset = get_user_model().objects.filter(
                is_active=True,
                nivel_permissao__in=["ADM", "FUNC"],
                employee__isnull=True,
            )
            self.fields["user"].label_from_instance = lambda user: user.username
